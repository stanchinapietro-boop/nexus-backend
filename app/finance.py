from typing import Literal
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, String, case, cast, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, SessionLocal, get_db

router = APIRouter(prefix="/api/finance", tags=["finance"])


class Account(Base):
    __tablename__ = "fin_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20), default="cash")
    initial_cents: Mapped[int] = mapped_column(Integer, default=0)


class Category(Base):
    __tablename__ = "fin_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    type: Mapped[str] = mapped_column(String(10))  # expense | income
    color: Mapped[str] = mapped_column(String(9), default="#ff6a1a")


class Transaction(Base):
    __tablename__ = "fin_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(10))
    amount_cents: Mapped[int] = mapped_column(Integer)  # sempre positivo
    day: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(String(300), default="")
    account_id: Mapped[int] = mapped_column(ForeignKey("fin_accounts.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("fin_categories.id"), nullable=True)


MAX_CENTS = 2_147_483_647

class FinanceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class AccountIn(FinanceInput):
    name: str = Field(min_length=1, max_length=80)
    kind: str = Field(default="cash", min_length=1, max_length=20)
    initial_cents: int = Field(default=0, ge=-2_147_483_648, le=MAX_CENTS)


class CategoryIn(FinanceInput):
    name: str = Field(min_length=1, max_length=60)
    type: str = Field(pattern="^(expense|income)$")
    color: str = Field(default="#ff6a1a", min_length=1, max_length=9)


class TxIn(BaseModel):
    type: str = Field(pattern="^(expense|income)$")
    amount_cents: int = Field(gt=0, le=MAX_CENTS)
    day: date
    note: str = Field(default="", max_length=300)
    account_id: int
    category_id: int | None = None


EXPENSE = [("Spesa", "#22c55e"), ("Ristoranti", "#f97316"), ("Casa", "#8b5cf6"), ("Bollette", "#eab308"),
           ("Trasporti", "#0ea5e9"), ("Salute", "#ef4444"), ("Svago", "#ec4899"), ("Abbonamenti", "#6366f1"),
           ("Shopping", "#d946ef"), ("Viaggi", "#14b8a6"), ("Istruzione", "#3b82f6"), ("Regali", "#f43f5e"),
           ("Altro", "#71717a")]
INCOME = [("Stipendio", "#22c55e"), ("Lavoro extra", "#14b8a6"), ("Altro", "#71717a")]


def seed():
    with SessionLocal() as db:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(select(func.pg_advisory_xact_lock(16023014, 3)))
        if db.scalar(select(Category.id).limit(1)) is None:
            db.add_all([Category(name=n, type="expense", color=c) for n, c in EXPENSE])
            db.add_all([Category(name=n, type="income", color=c) for n, c in INCOME])
        if db.scalar(select(Account.id).limit(1)) is None:
            db.add(Account(name="Contanti", kind="cash"))
        db.commit()
        process_recurring(db)


def balance(db: Session, a: Account) -> int:
    total = a.initial_cents
    for t in db.scalars(select(Transaction).where(Transaction.account_id == a.id)):
        total += t.amount_cents if t.type == "income" else -t.amount_cents
    return total


def acc_out(db, a):
    n = len(db.scalars(select(Transaction.id).where(Transaction.account_id == a.id)).all())
    return {"id": a.id, "name": a.name, "kind": a.kind, "initial_cents": a.initial_cents,
            "balance_cents": balance(db, a), "tx_count": n}


def tx_out(db, t):
    c = db.get(Category, t.category_id) if t.category_id else None
    a = db.get(Account, t.account_id)
    return {"id": t.id, "type": t.type, "amount_cents": t.amount_cents, "day": t.day.isoformat(),
            "note": t.note, "account_id": t.account_id, "account_name": a.name if a else "",
            "category_id": t.category_id, "category_name": c.name if c else "Senza categoria",
            "category_color": c.color if c else "#71717a"}


def month_range(month: str | None):
    m = month or datetime.now().strftime("%Y-%m")
    try:
        y, mo = map(int, m.split("-"))
        start = date(y, mo, 1)
        end = date(y + (mo == 12), mo % 12 + 1, 1)
    except ValueError:
        raise HTTPException(422, "Mese non valido (usa AAAA-MM)")
    return start, end


@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    process_recurring(db)
    return [acc_out(db, a) for a in db.scalars(select(Account).order_by(Account.id))]


@router.post("/accounts", status_code=201)
def create_account(d: AccountIn, db: Session = Depends(get_db)):
    a = Account(**d.model_dump()); db.add(a); db.commit()
    return acc_out(db, a)


@router.delete("/accounts/{i}", status_code=204)
def delete_account(i: int, db: Session = Depends(get_db)):
    a = db.get(Account, i, with_for_update=True)
    if not a: raise HTTPException(404, "Conto non trovato")
    if db.scalar(select(Transaction.id).where(Transaction.account_id == i).limit(1)):
        raise HTTPException(409, "Il conto ha dei movimenti: eliminali prima")
    if db.scalar(select(Recurring.id).where(Recurring.account_id == i).limit(1)):
        raise HTTPException(409, "Il conto è collegato a una ricorrenza.")
    db.delete(a); db.commit()


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "type": c.type, "color": c.color}
            for c in db.scalars(select(Category).order_by(Category.id))]


@router.post("/categories", status_code=201)
def create_category(d: CategoryIn, db: Session = Depends(get_db)):
    c = Category(**d.model_dump()); db.add(c); db.commit()
    return {"id": c.id, "name": c.name, "type": c.type, "color": c.color}


@router.delete("/categories/{i}", status_code=204)
def delete_category(i: int, db: Session = Depends(get_db)):
    c = db.get(Category, i, with_for_update=True)
    if not c: raise HTTPException(404, "Categoria non trovata")
    if db.scalar(select(Budget.id).where(Budget.category_id == i).limit(1)):
        raise HTTPException(409, "La categoria è usata da un budget.")
    if db.scalar(select(Recurring.id).where(Recurring.category_id == i).limit(1)):
        raise HTTPException(409, "La categoria è usata da una ricorrenza.")
    db.execute(update(Transaction).where(Transaction.category_id == i).values(category_id=None))
    db.delete(c); db.commit()


@router.get("/transactions")
def list_transactions(month: str | None = None, q: str = "", account_id: int | None = None,
                      category_id: int | None = None, type: Literal["expense", "income"] | None = None,
                      db: Session = Depends(get_db)):
    process_recurring(db)
    s, e = month_range(month)
    statement = select(Transaction).where(Transaction.day >= s, Transaction.day < e)
    if account_id is not None:
        statement = statement.where(Transaction.account_id == account_id)
    if category_id is not None:
        statement = statement.where(Transaction.category_id == category_id)
    if type:
        statement = statement.where(Transaction.type == type)
    rows = db.scalars(statement.order_by(Transaction.day.desc(), Transaction.id.desc())).all()
    out = [tx_out(db, t) for t in rows]
    if q:
        ql = q.lower()
        out = [t for t in out if ql in t["note"].lower() or ql in t["category_name"].lower()]
    return out


def validate_links(db: Session, account_id: int, category_id: int | None, kind: str):
    # FOR KEY SHARE allows parallel ledger inserts while protecting parent references.
    lock = {"read": True, "key_share": True}
    if not db.get(Account, account_id, with_for_update=lock):
        raise HTTPException(422, "Conto inesistente")
    if category_id is not None:
        category = db.get(Category, category_id, with_for_update=lock)
        if not category or category.type != kind:
            raise HTTPException(422, "Scegli una categoria compatibile con il tipo di movimento.")


@router.post("/transactions", status_code=201)
def create_transaction(d: TxIn, db: Session = Depends(get_db)):
    validate_links(db, d.account_id, d.category_id, d.type)
    t = Transaction(type=d.type, amount_cents=d.amount_cents, day=d.day, note=d.note,
                    account_id=d.account_id, category_id=d.category_id)
    db.add(t); db.commit()
    return tx_out(db, t)


@router.delete("/transactions/{i}", status_code=204)
def delete_transaction(i: int, db: Session = Depends(get_db)):
    t = db.get(Transaction, i)
    if not t: raise HTTPException(404, "Movimento non trovato")
    db.delete(t); db.commit()


@router.get("/summary")
def summary(month: str | None = None, db: Session = Depends(get_db)):
    process_recurring(db)
    s, e = month_range(month)
    accounts = [acc_out(db, a) for a in db.scalars(select(Account))]
    rows = db.scalars(select(Transaction).where(Transaction.day >= s, Transaction.day < e)).all()
    inc = sum(t.amount_cents for t in rows if t.type == "income")
    exp = sum(t.amount_cents for t in rows if t.type == "expense")
    cats: dict[int | None, dict] = {}
    for t in rows:
        if t.type != "expense": continue
        o = tx_out(db, t)
        c = cats.setdefault(t.category_id, {"category_id": t.category_id, "name": o["category_name"], "color": o["category_color"], "cents": 0})
        c["cents"] += t.amount_cents
    recent = db.scalars(select(Transaction).where(Transaction.day >= s, Transaction.day < e).order_by(Transaction.day.desc(), Transaction.id.desc()).limit(5)).all()
    return {"balance_cents": sum(a["balance_cents"] for a in accounts), "income_cents": inc,
            "expense_cents": exp, "by_category": sorted(cats.values(), key=lambda c: -c["cents"]),
            "recent": [tx_out(db, t) for t in recent], "accounts": accounts}


class Budget(Base):
    __tablename__ = "fin_budgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("fin_categories.id"), unique=True)
    limit_cents: Mapped[int] = mapped_column(Integer)


class BudgetIn(BaseModel):
    category_id: int
    limit_cents: int = Field(gt=0, le=MAX_CENTS)


@router.get("/budgets")
def list_budgets(month: str | None = None, db: Session = Depends(get_db)):
    s, e = month_range(month)
    process_recurring(db)
    out = []
    for b in db.scalars(select(Budget).order_by(Budget.id)):
        c = db.get(Category, b.category_id)
        spent = sum(t.amount_cents for t in db.scalars(select(Transaction).where(
            Transaction.category_id == b.category_id, Transaction.type == "expense",
            Transaction.day >= s, Transaction.day < e)))
        out.append({"id": b.id, "category_id": b.category_id, "category_name": c.name if c else "?",
                    "color": c.color if c else "#71717a", "limit_cents": b.limit_cents, "spent_cents": spent})
    return out


@router.post("/budgets", status_code=201)
def set_budget(d: BudgetIn, db: Session = Depends(get_db)):
    c = db.get(Category, d.category_id, with_for_update={"read": True, "key_share": True})
    if not c or c.type != "expense":
        raise HTTPException(422, "Scegli una categoria di spesa")
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    stmt = insert(Budget).values(category_id=d.category_id, limit_cents=d.limit_cents)
    db.execute(stmt.on_conflict_do_update(index_elements=[Budget.category_id],
                                         set_={"limit_cents": d.limit_cents}))
    db.commit()
    return {"ok": True}


@router.delete("/budgets/{i}", status_code=204)
def delete_budget(i: int, db: Session = Depends(get_db)):
    b = db.get(Budget, i)
    if not b: raise HTTPException(404, "Budget non trovato")
    db.delete(b); db.commit()


@router.get("/report")
def report(periods: int = 6, db: Session = Depends(get_db)):
    periods = max(1, min(periods, 24))
    process_recurring(db)
    txs = db.scalars(select(Transaction)).all()
    initial = sum(a.initial_cents for a in db.scalars(select(Account)))
    sign = lambda t: t.amount_cents if t.type == "income" else -t.amount_cents
    today = date.today()
    out = []
    for i in range(periods - 1, -1, -1):
        y, m = divmod(today.year * 12 + today.month - 1 - i, 12)
        s, e = date(y, m + 1, 1), date(y + (m == 11), (m + 1) % 12 + 1, 1)
        inm = [t for t in txs if s <= t.day < e]
        account_balance = initial + sum(sign(t) for t in txs if t.day < e)
        out.append({"month": s.strftime("%Y-%m"),
                    "income_cents": sum(t.amount_cents for t in inm if t.type == "income"),
                    "expense_cents": sum(t.amount_cents for t in inm if t.type == "expense"),
                    "accounts_balance_cents": account_balance,
                    "net_worth_cents": account_balance})
    return out


class Goal(Base):
    __tablename__ = "fin_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    target_cents: Mapped[int] = mapped_column(Integer)
    saved_cents: Mapped[int] = mapped_column(Integer, default=0)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)


class Recurring(Base):
    __tablename__ = "fin_recurring"
    id: Mapped[int] = mapped_column(primary_key=True)
    note: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(10))
    amount_cents: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(ForeignKey("fin_accounts.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("fin_categories.id"), nullable=True)
    freq: Mapped[str] = mapped_column(String(10))  # weekly | monthly | yearly
    next_day: Mapped[date] = mapped_column(Date)
    anchor_day: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class GoalIn(FinanceInput):
    name: str = Field(min_length=1, max_length=80)
    target_cents: int = Field(gt=0, le=MAX_CENTS)
    deadline: date | None = None


class DeltaIn(BaseModel):
    delta_cents: int = Field(ge=-2_147_483_648, le=MAX_CENTS)


class RecIn(FinanceInput):
    note: str = Field(min_length=1, max_length=120)
    type: str = Field(pattern="^(expense|income)$")
    amount_cents: int = Field(gt=0, le=MAX_CENTS)
    account_id: int
    category_id: int | None = None
    freq: str = Field(pattern="^(weekly|monthly|yearly)$")
    start: date


def advance(d: date, freq: str, anchor: int) -> date:
    if freq == "weekly":
        return d + timedelta(days=7)
    idx = d.year * 12 + d.month - 1 + (1 if freq == "monthly" else 12)
    y, m = divmod(idx, 12)
    m += 1
    last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
    return date(y, m, min(anchor, last))


def process_recurring(db: Session):
    today, made = date.today(), 0
    due = select(Recurring).where(Recurring.active.is_(True), Recurring.next_day <= today)
    for r in db.scalars(due.order_by(Recurring.next_day, Recurring.id)):
        if made >= 500:
            break
        cursor = r.next_day
        dates = []
        while cursor <= today and made + len(dates) < 500:
            dates.append(cursor)
            cursor = advance(cursor, r.freq, r.anchor_day)
        # The cursor and all its ledger entries are committed together. A second
        # worker that read the old cursor loses this claim and writes nothing.
        claim = update(Recurring).where(Recurring.id == r.id, Recurring.active.is_(True),
                                        Recurring.next_day == r.next_day).values(next_day=cursor)
        if db.execute(claim.execution_options(synchronize_session=False)).rowcount == 1:
            for day in dates:
                db.add(Transaction(type=r.type, amount_cents=r.amount_cents, day=day, note=r.note,
                                   account_id=r.account_id, category_id=r.category_id))
            made += len(dates)
            db.expire(r, ["next_day"])
    db.commit()


def goal_out(g: Goal):
    return {"id": g.id, "name": g.name, "target_cents": g.target_cents, "saved_cents": g.saved_cents,
            "deadline": g.deadline.isoformat() if g.deadline else None}


def rec_out(db, r: Recurring):
    c = db.get(Category, r.category_id) if r.category_id else None
    a = db.get(Account, r.account_id)
    return {"id": r.id, "note": r.note, "type": r.type, "amount_cents": r.amount_cents, "freq": r.freq,
            "account_id": r.account_id, "category_id": r.category_id, "anchor_day": r.anchor_day,
            "next_day": r.next_day.isoformat(), "active": r.active, "account_name": a.name if a else "",
            "category_name": c.name if c else "Senza categoria"}


@router.get("/goals")
def list_goals(db: Session = Depends(get_db)):
    return [goal_out(g) for g in db.scalars(select(Goal).order_by(Goal.id))]


@router.post("/goals", status_code=201)
def create_goal(d: GoalIn, db: Session = Depends(get_db)):
    g = Goal(**d.model_dump()); db.add(g); db.commit()
    return goal_out(g)


@router.post("/goals/{i}/add")
def goal_add(i: int, d: DeltaIn, db: Session = Depends(get_db)):
    total = cast(Goal.saved_cents, BigInteger) + d.delta_cents
    stmt = (update(Goal).where(Goal.id == i, total <= MAX_CENTS)
            .values(saved_cents=case((total < 0, 0), else_=total)).returning(Goal))
    goal = db.scalar(stmt.execution_options(synchronize_session=False))
    if goal is None:
        if not db.get(Goal, i):
            raise HTTPException(404, "Obiettivo non trovato")
        raise HTTPException(422, "Importo accumulato troppo elevato.")
    result = goal_out(goal)
    db.commit()
    return result


@router.delete("/goals/{i}", status_code=204)
def delete_goal(i: int, db: Session = Depends(get_db)):
    g = db.get(Goal, i)
    if not g: raise HTTPException(404, "Obiettivo non trovato")
    db.delete(g); db.commit()


@router.get("/recurring")
def list_recurring(db: Session = Depends(get_db)):
    process_recurring(db)
    return [rec_out(db, r) for r in db.scalars(select(Recurring).order_by(Recurring.id))]


@router.post("/recurring", status_code=201)
def create_recurring(d: RecIn, db: Session = Depends(get_db)):
    validate_links(db, d.account_id, d.category_id, d.type)
    r = Recurring(note=d.note, type=d.type, amount_cents=d.amount_cents, account_id=d.account_id,
                  category_id=d.category_id, freq=d.freq, next_day=d.start, anchor_day=d.start.day)
    db.add(r); db.flush()
    process_recurring(db)
    return rec_out(db, r)


@router.post("/recurring/{i}/toggle")
def toggle_recurring(i: int, db: Session = Depends(get_db)):
    r = db.scalar(update(Recurring).where(Recurring.id == i).values(active=~Recurring.active).returning(Recurring))
    if not r: raise HTTPException(404, "Ricorrente non trovato")
    db.commit()
    return rec_out(db, r)


@router.delete("/recurring/{i}", status_code=204)
def delete_recurring(i: int, db: Session = Depends(get_db)):
    r = db.get(Recurring, i)
    if not r: raise HTTPException(404, "Ricorrente non trovato")
    db.delete(r); db.commit()


@router.put("/transactions/{i}")
def update_transaction(i: int, d: TxIn, db: Session = Depends(get_db)):
    t = db.get(Transaction, i)
    if not t: raise HTTPException(404, "Movimento non trovato")
    validate_links(db, d.account_id, d.category_id, d.type)
    t.type, t.amount_cents, t.day, t.note = d.type, d.amount_cents, d.day, d.note
    t.account_id, t.category_id = d.account_id, d.category_id
    db.commit()
    return tx_out(db, t)


@router.put("/accounts/{i}")
def update_account(i: int, d: AccountIn, db: Session = Depends(get_db)):
    a = db.get(Account, i)
    if not a: raise HTTPException(404, "Conto non trovato")
    a.name, a.kind, a.initial_cents = d.name, d.kind, d.initial_cents
    db.commit()
    return acc_out(db, a)


@router.put("/categories/{i}")
def update_category(i: int, d: CategoryIn, db: Session = Depends(get_db)):
    c = db.get(Category, i)
    if not c: raise HTTPException(404, "Categoria non trovata")
    if d.type != c.type:
        raise HTTPException(422, "Il tipo di una categoria esistente è fisso.")
    c.name, c.color = d.name, d.color
    db.commit()
    return {"id": c.id, "name": c.name, "type": c.type, "color": c.color}


@router.get("/export")
def export_all(db: Session = Depends(get_db)):
    process_recurring(db)
    return {
        "exported_at": datetime.now().isoformat(),
        "accounts": [acc_out(db, a) for a in db.scalars(select(Account))],
        "categories": [{"id": c.id, "name": c.name, "type": c.type, "color": c.color} for c in db.scalars(select(Category))],
        "transactions": [tx_out(db, t) for t in db.scalars(select(Transaction).order_by(Transaction.day))],
        "budgets": [{"category_id": b.category_id, "limit_cents": b.limit_cents} for b in db.scalars(select(Budget))],
        "goals": [goal_out(g) for g in db.scalars(select(Goal))],
        "recurring": [rec_out(db, r) for r in db.scalars(select(Recurring))],
    }

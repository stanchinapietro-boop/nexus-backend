"""Moduli Life condivisi con la variante Desktop."""
from datetime import date, datetime, timezone
from calendar import monthrange

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, get_db

router = APIRouter(prefix="/api/life", tags=["life-planner"])


class PersonalGoal(Base):
    __tablename__ = "life_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(30), default="personal")
    goal_type: Mapped[str] = mapped_column(String(16), default="completion")
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(30), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    motivation: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(default=True)

class Habit(Base):
    __tablename__ = "life_habits"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(30), default="personal")
    kind: Mapped[str] = mapped_column(String(12), default="binary")
    days: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4,5,6")
    target_value: Mapped[float] = mapped_column(Float, default=1)
    unit: Mapped[str] = mapped_column(String(30), default="")
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    active: Mapped[bool] = mapped_column(default=True)

class HabitLog(Base):
    __tablename__ = "life_habit_logs"
    __table_args__ = (UniqueConstraint("habit_id", "day", name="uq_life_habit_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("life_habits.id"))
    day: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float, default=1)
    completed: Mapped[bool] = mapped_column(default=True)
    note: Mapped[str] = mapped_column(String(300), default="")

class Routine(Base):
    __tablename__ = "life_routines"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30), default="custom")
    days: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4,5,6")
    active: Mapped[bool] = mapped_column(default=True)

class RoutineStep(Base):
    __tablename__ = "life_routine_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("life_routines.id"))
    title: Mapped[str] = mapped_column(String(140))
    position: Mapped[int] = mapped_column(Integer, default=0)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)

class RoutineLog(Base):
    __tablename__ = "life_routine_logs"
    __table_args__ = (UniqueConstraint("routine_id", "day", name="uq_life_routine_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("life_routines.id"))
    day: Mapped[date] = mapped_column(Date)
    completed_steps: Mapped[str] = mapped_column(String(2000), default="")

class Workout(Base):
    __tablename__ = "life_workouts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    sport: Mapped[str] = mapped_column(String(40))
    day: Mapped[date] = mapped_column(Date)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    place: Mapped[str] = mapped_column(String(180), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    intensity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    completed: Mapped[bool] = mapped_column(default=False)

class WorkoutExercise(Base):
    __tablename__ = "life_workout_exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("life_workouts.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(140))
    muscle_group: Mapped[str] = mapped_column(String(60), default="")
    sets: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")

class GoalMilestone(Base):
    __tablename__ = "life_goal_milestones"
    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("life_goals.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed: Mapped[bool] = mapped_column(default=False)

class GoalIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=5000)
    category: str = Field(default="personal", max_length=30)
    goal_type: str = Field(default="completion", pattern="^(numeric|frequency|milestone|completion)$")
    target_value: float | None = Field(default=None, gt=0)
    current_value: float = Field(default=0, ge=0)
    unit: str = Field(default="", max_length=30)
    due_date: date | None = None
    motivation: str = Field(default="", max_length=3000)

class HabitIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="personal", max_length=30)
    kind: str = Field(default="binary", pattern="^(binary|numeric|duration|negative)$")
    days: list[int] = Field(default_factory=lambda: list(range(7)), max_length=7)
    target_value: float = Field(default=1, gt=0)
    unit: str = Field(default="", max_length=30)
    start_date: date = Field(default_factory=date.today)

class HabitLogIn(BaseModel):
    value: float = Field(default=1, ge=0)
    completed: bool = True
    note: str = Field(default="", max_length=300)

class RoutineIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="custom", max_length=30)
    days: list[int] = Field(default_factory=lambda: list(range(7)), max_length=7)

class RoutineStepIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    duration_minutes: int = Field(default=0, ge=0, le=1440)

class WorkoutIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    sport: str = Field(min_length=1, max_length=40)
    day: date
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    place: str = Field(default="", max_length=180)
    description: str = Field(default="", max_length=4000)
    intensity: int | None = Field(default=None, ge=1, le=10)
    notes: str = Field(default="", max_length=4000)

class WorkoutSetIn(BaseModel):
    reps: int | None = Field(default=None, ge=0, le=10000)
    weight: float | None = Field(default=None, ge=0, le=10000)
    rest_seconds: int | None = Field(default=None, ge=0, le=3600)

class WorkoutExerciseIn(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    muscle_group: str = Field(default="", max_length=60)
    sets: list[WorkoutSetIn] = Field(default_factory=list, max_length=100)
    notes: str = Field(default="", max_length=3000)

class MilestoneIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    due_date: date | None = None

def days_value(days: list[int]) -> str:
    if any(day < 0 or day > 6 for day in days):
        raise HTTPException(422, "I giorni devono essere compresi tra 0 e 6")
    return ",".join(map(str, sorted(set(days))))

@router.get("/goals")
def list_goals(db:Session=Depends(get_db)):
    result=[]
    for g in db.scalars(select(PersonalGoal).order_by(PersonalGoal.id.desc())):
        progress=None
        if g.goal_type in {"numeric","frequency"} and g.target_value:
            progress=min(100,round(g.current_value/g.target_value*100))
        elif g.goal_type=="completion":progress=100 if g.current_value>=1 else 0
        elif g.goal_type=="milestone":
            milestones=db.scalars(select(GoalMilestone).where(GoalMilestone.goal_id==g.id)).all()
            progress=round(sum(m.completed for m in milestones)/len(milestones)*100) if milestones else None
        result.append({"id":g.id,"title":g.title,"description":g.description,"category":g.category,"goal_type":g.goal_type,
            "target_value":g.target_value,"current_value":g.current_value,"unit":g.unit,"due_date":g.due_date.isoformat() if g.due_date else None,
            "motivation":g.motivation,"active":g.active,"progress":progress})
    return result

@router.post("/goals/{goal_id}/complete")
def complete_goal(goal_id:int,db:Session=Depends(get_db)):
    row=db.get(PersonalGoal,goal_id)
    if not row:raise HTTPException(404,"Obiettivo non trovato")
    if row.goal_type!="completion":raise HTTPException(422,"Solo un obiettivo di completamento può essere chiuso direttamente")
    row.current_value=0 if row.current_value>=1 else 1
    row.active=row.current_value<1
    db.commit()
    return next(g for g in list_goals(db) if g["id"]==row.id)

@router.post("/goals",status_code=201)
def create_goal(data:GoalIn,db:Session=Depends(get_db)):
    row=PersonalGoal(**data.model_dump());db.add(row);db.commit();db.refresh(row);return next(g for g in list_goals(db) if g["id"]==row.id)

@router.put("/goals/{goal_id}")
def update_goal(goal_id:int,data:GoalIn,db:Session=Depends(get_db)):
    row=db.get(PersonalGoal,goal_id)
    if not row:raise HTTPException(404,"Obiettivo non trovato")
    for key,value in data.model_dump().items():setattr(row,key,value)
    db.commit();return next(g for g in list_goals(db) if g["id"]==row.id)

@router.delete("/goals/{goal_id}",status_code=204)
def delete_goal(goal_id:int,db:Session=Depends(get_db)):
    row=db.get(PersonalGoal,goal_id)
    if not row:raise HTTPException(404,"Obiettivo non trovato")
    db.query(GoalMilestone).filter(GoalMilestone.goal_id==goal_id).delete(synchronize_session=False)
    db.delete(row);db.commit()

def habit_out(db:Session,row:Habit):
    today=date.today();scheduled=today>=row.start_date and today.weekday() in {int(x) for x in row.days.split(",") if x}
    log=db.scalar(select(HabitLog).where(HabitLog.habit_id==row.id,HabitLog.day==today))
    streak=0;cursor=today
    if scheduled and not (log and log.completed):cursor=cursor.fromordinal(cursor.toordinal()-1)
    while cursor>=row.start_date:
        if cursor.weekday() not in {int(x) for x in row.days.split(",") if x}:cursor=cursor.fromordinal(cursor.toordinal()-1);continue
        done=db.scalar(select(HabitLog.id).where(HabitLog.habit_id==row.id,HabitLog.day==cursor,HabitLog.completed.is_(True)))
        if not done:break
        streak+=1;cursor=cursor.fromordinal(cursor.toordinal()-1)
    return {"id":row.id,"name":row.name,"description":row.description,"category":row.category,"kind":row.kind,
        "days":[int(x) for x in row.days.split(",") if x],"target_value":row.target_value,"unit":row.unit,
        "start_date":row.start_date.isoformat(),"active":row.active,"scheduled_today":scheduled,
        "today_value":log.value if log else 0,"today_completed":log.completed if log else False,"streak":streak}

@router.get("/habits")
def list_habits(db:Session=Depends(get_db)):
    return [habit_out(db,row) for row in db.scalars(select(Habit).where(Habit.active.is_(True)).order_by(Habit.id))]

@router.post("/habits",status_code=201)
def create_habit(data:HabitIn,db:Session=Depends(get_db)):
    row=Habit(**{**data.model_dump(exclude={"days"}),"days":days_value(data.days)});db.add(row);db.commit();db.refresh(row);return habit_out(db,row)

@router.put("/habits/{habit_id}")
def update_habit(habit_id:int,data:HabitIn,db:Session=Depends(get_db)):
    row=db.get(Habit,habit_id)
    if not row:raise HTTPException(404,"Abitudine non trovata")
    for key,value in data.model_dump(exclude={"days"}).items():setattr(row,key,value)
    row.days=days_value(data.days);db.commit();return habit_out(db,row)

@router.post("/habits/{habit_id}/log")
def log_habit(habit_id:int,data:HabitLogIn,day:date|None=None,db:Session=Depends(get_db)):
    habit=db.get(Habit,habit_id)
    if not habit:raise HTTPException(404,"Abitudine non trovata")
    log_day=day or date.today()
    if log_day<habit.start_date or log_day.weekday() not in {int(x) for x in habit.days.split(",") if x}:raise HTTPException(422,"Abitudine non prevista in questo giorno")
    row=db.scalar(select(HabitLog).where(HabitLog.habit_id==habit_id,HabitLog.day==log_day))
    if not row:row=HabitLog(habit_id=habit_id,day=log_day);db.add(row)
    achieved=data.completed
    if habit.kind in {"numeric","duration"}:achieved=achieved and data.value>=habit.target_value
    elif habit.kind=="negative":achieved=achieved and data.value<=habit.target_value
    row.value=data.value;row.completed=achieved;row.note=data.note;db.commit();return habit_out(db,habit)

@router.get("/habits/{habit_id}/history")
def habit_history(habit_id:int,db:Session=Depends(get_db)):
    if not db.get(Habit,habit_id):raise HTTPException(404,"Abitudine non trovata")
    return [{"day":r.day.isoformat(),"value":r.value,"completed":r.completed,"note":r.note}
        for r in db.scalars(select(HabitLog).where(HabitLog.habit_id==habit_id).order_by(HabitLog.day.desc()).limit(366))]

@router.delete("/habits/{habit_id}",status_code=204)
def delete_habit(habit_id:int,db:Session=Depends(get_db)):
    row=db.get(Habit,habit_id)
    if not row:raise HTTPException(404,"Abitudine non trovata")
    row.active=False;db.commit()

@router.get("/routines")
def list_routines(db:Session=Depends(get_db)):
    result=[]
    today=date.today()
    for routine in db.scalars(select(Routine).where(Routine.active.is_(True)).order_by(Routine.id)):
        steps=db.scalars(select(RoutineStep).where(RoutineStep.routine_id==routine.id).order_by(RoutineStep.position)).all()
        log=db.scalar(select(RoutineLog).where(RoutineLog.routine_id==routine.id,RoutineLog.day==today))
        result.append({"id":routine.id,"name":routine.name,"kind":routine.kind,"days":[int(x) for x in routine.days.split(",") if x],
            "completed_steps":[int(x) for x in (log.completed_steps.split(",") if log and log.completed_steps else [])],
            "steps":[{"id":s.id,"title":s.title,"position":s.position,"duration_minutes":s.duration_minutes} for s in steps]})
    return result

@router.post("/routines",status_code=201)
def create_routine(data:RoutineIn,db:Session=Depends(get_db)):
    row=Routine(name=data.name,kind=data.kind,days=days_value(data.days));db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"name":row.name,"kind":row.kind,"days":data.days,"steps":[]}

@router.post("/routines/{routine_id}/steps",status_code=201)
def add_routine_step(routine_id:int,data:RoutineStepIn,db:Session=Depends(get_db)):
    if not db.get(Routine,routine_id):raise HTTPException(404,"Routine non trovata")
    db.get(Routine,routine_id,with_for_update=True)
    count=len(db.scalars(select(RoutineStep.id).where(RoutineStep.routine_id==routine_id)).all())
    row=RoutineStep(routine_id=routine_id,title=data.title,position=count,duration_minutes=data.duration_minutes);db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"title":row.title,"position":row.position,"duration_minutes":row.duration_minutes}

class RoutineOrder(BaseModel):
    expected: list[int] = Field(max_length=500)
    ordered: list[int] = Field(max_length=500)


@router.put("/routines/{routine_id}/order", status_code=204)
def reorder_steps(routine_id: int, body: RoutineOrder, db: Session = Depends(get_db)):
    if not db.get(Routine, routine_id, with_for_update=True):
        raise HTTPException(404, "Routine non trovata")
    steps = db.scalars(select(RoutineStep).where(RoutineStep.routine_id == routine_id)
                       .order_by(RoutineStep.position, RoutineStep.id)).all()
    by_id = {step.id: step for step in steps}
    if list(by_id) != body.expected:
        raise HTTPException(409, "La routine è cambiata. Ricarica i passi.")
    if sorted(body.ordered) != sorted(by_id):
        raise HTTPException(422, "Inserisci ogni passo una sola volta")
    for position, step_id in enumerate(body.ordered):
        by_id[step_id].position = position
    db.commit()


@router.post("/routines/{routine_id}/complete")
def complete_routine_step(routine_id:int,step_id:int,db:Session=Depends(get_db)):
    if not db.get(Routine,routine_id):raise HTTPException(404,"Routine non trovata")
    if not db.scalar(select(RoutineStep.id).where(RoutineStep.id==step_id,RoutineStep.routine_id==routine_id)):
        raise HTTPException(404,"Passo non trovato in questa routine")
    today=date.today();row=db.scalar(select(RoutineLog).where(RoutineLog.routine_id==routine_id,RoutineLog.day==today))
    if not row:row=RoutineLog(routine_id=routine_id,day=today);db.add(row);db.flush()
    completed={int(x) for x in row.completed_steps.split(",") if x}
    if step_id in completed:completed.remove(step_id)
    else:completed.add(step_id)
    row.completed_steps=",".join(map(str,sorted(completed)));db.commit()
    total=len(db.scalars(select(RoutineStep.id).where(RoutineStep.routine_id==routine_id)).all())
    return {"routine_id":routine_id,"day":today.isoformat(),"completed_steps":sorted(completed),"total_steps":total,"progress":round(len(completed)/total*100) if total else 0}

@router.get("/workouts")
def workouts(db:Session=Depends(get_db)):
    return [{"id":r.id,"name":r.name,"sport":r.sport,"day":r.day.isoformat(),"duration_minutes":r.duration_minutes,"place":r.place,"description":r.description,"intensity":r.intensity,"notes":r.notes,"completed":r.completed} for r in db.scalars(select(Workout).order_by(Workout.day.desc()))]

@router.post("/workouts",status_code=201)
def create_workout(data:WorkoutIn,db:Session=Depends(get_db)):
    row=Workout(**data.model_dump());db.add(row);db.commit();db.refresh(row);return {"id":row.id,**data.model_dump(),"completed":row.completed}

@router.put("/workouts/{workout_id}")
def update_workout(workout_id: int, data: WorkoutIn, db: Session = Depends(get_db)):
    row = db.get(Workout, workout_id, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Allenamento non trovato")
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return {"id": row.id, **data.model_dump(), "completed": row.completed}

@router.post("/workouts/{workout_id}/complete")
def complete_workout(workout_id:int,db:Session=Depends(get_db)):
    row=db.get(Workout,workout_id)
    if not row:raise HTTPException(404,"Allenamento non trovato")
    row.completed=not row.completed;db.commit();return {"id":row.id,"completed":row.completed}

@router.delete("/workouts/{workout_id}",status_code=204)
def delete_workout(workout_id:int,db:Session=Depends(get_db)):
    row=db.get(Workout,workout_id)
    if not row:raise HTTPException(404,"Allenamento non trovato")
    db.query(WorkoutExercise).filter(WorkoutExercise.workout_id==workout_id).delete(synchronize_session=False)
    db.delete(row);db.commit()

@router.get("/workouts/{workout_id}/exercises")
def workout_exercises(workout_id:int,db:Session=Depends(get_db)):
    if not db.get(Workout,workout_id):raise HTTPException(404,"Allenamento non trovato")
    return [{"id":x.id,"name":x.name,"muscle_group":x.muscle_group,"sets":x.sets,"notes":x.notes} for x in db.scalars(select(WorkoutExercise).where(WorkoutExercise.workout_id==workout_id).order_by(WorkoutExercise.id))]

@router.post("/workouts/{workout_id}/exercises",status_code=201)
def add_workout_exercise(workout_id:int,data:WorkoutExerciseIn,db:Session=Depends(get_db)):
    if not db.get(Workout,workout_id):raise HTTPException(404,"Allenamento non trovato")
    row=WorkoutExercise(workout_id=workout_id,**data.model_dump());db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,**data.model_dump()}

@router.delete("/workout-exercises/{exercise_id}",status_code=204)
def delete_workout_exercise(exercise_id:int,db:Session=Depends(get_db)):
    row=db.get(WorkoutExercise,exercise_id)
    if not row:raise HTTPException(404,"Esercizio non trovato")
    db.delete(row);db.commit()

@router.get("/goals/{goal_id}/milestones")
def list_milestones(goal_id:int,db:Session=Depends(get_db)):
    if not db.get(PersonalGoal,goal_id):raise HTTPException(404,"Obiettivo non trovato")
    return [{"id":m.id,"title":m.title,"due_date":m.due_date.isoformat() if m.due_date else None,"completed":m.completed} for m in db.scalars(select(GoalMilestone).where(GoalMilestone.goal_id==goal_id).order_by(GoalMilestone.due_date,GoalMilestone.id))]

@router.post("/goals/{goal_id}/milestones",status_code=201)
def create_milestone(goal_id:int,data:MilestoneIn,db:Session=Depends(get_db)):
    if not db.get(PersonalGoal,goal_id):raise HTTPException(404,"Obiettivo non trovato")
    row=GoalMilestone(goal_id=goal_id,**data.model_dump());db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"title":row.title,"due_date":row.due_date.isoformat() if row.due_date else None,"completed":row.completed}

@router.post("/milestones/{milestone_id}/toggle")
def toggle_milestone(milestone_id:int,db:Session=Depends(get_db)):
    row=db.get(GoalMilestone,milestone_id)
    if not row:raise HTTPException(404,"Milestone non trovata")
    row.completed=not row.completed;db.commit();return {"id":row.id,"completed":row.completed}

@router.delete("/milestones/{milestone_id}",status_code=204)
def delete_milestone(milestone_id:int,db:Session=Depends(get_db)):
    row=db.get(GoalMilestone,milestone_id)
    if not row:raise HTTPException(404,"Milestone non trovata")
    db.delete(row);db.commit()

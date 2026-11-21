"""Apply versioned Core OS migrations to an existing NEXUS PostgreSQL database."""
import hashlib
import os
from pathlib import Path

import psycopg


def migrate(url: str) -> list[str]:
    applied = []
    directory = Path(__file__).resolve().parents[1] / "migrations"
    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://", 1)) as db:
        db.execute("SELECT pg_advisory_xact_lock(16023014, 2)")
        if db.execute("SELECT to_regclass('public.notes')").fetchone()[0] is None:
            raise RuntimeError("Manca la tabella notes del progetto NEXUS. Verifica il database selezionato.")
        db.execute("CREATE TABLE IF NOT EXISTS public.nexus_core_migrations (version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
        db.execute("ALTER TABLE public.nexus_core_migrations ENABLE ROW LEVEL SECURITY")
        for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            prior = db.execute("SELECT checksum FROM public.nexus_core_migrations WHERE version=%s", (path.stem,)).fetchone()
            if prior:
                if prior[0] != checksum:
                    raise RuntimeError(f"La migrazione {path.name} è cambiata dopo l’applicazione.")
                continue
            # Il runner mantiene un'unica transazione per DDL, vincoli e registro.
            db.execute(sql)
            db.execute("INSERT INTO public.nexus_core_migrations(version, checksum) VALUES (%s,%s)", (path.stem, checksum))
            applied.append(path.name)
    return applied


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", required=True, help="Apply the migrations using DATABASE_URL")
    parser.parse_args()
    print("Migrazioni applicate:", ", ".join(migrate(os.environ["DATABASE_URL"])) or "già aggiornato")

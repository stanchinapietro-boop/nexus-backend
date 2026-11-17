# NEXUS LIFE OS — backend

API FastAPI pensata per Vercel, con database Postgres (Neon).
La password di accesso non è nel codice: nel database c'è solo il suo hash.

## Variabili d'ambiente (Vercel → Settings → Environment Variables)
- `DATABASE_URL`: arriva da sola collegando Neon (Storage).
- `SESSION_SECRET`: stringa casuale di almeno 32 caratteri.
- `SETUP_CODE`: almeno 16 caratteri casuali, serve solo la prima volta per creare la password.
- `TICKTICK_TOKEN` e `TICKTICK_TIMEZONE`.

Non scrivere mai questi valori nel codice o su GitHub.

## Prova in locale
```
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env      (compila SESSION_SECRET e SETUP_CODE)
.venv\Scripts\python -m uvicorn app.main:app --reload
.venv\Scripts\python -m pytest
```

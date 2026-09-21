# Payment Gateway API

A production-oriented FastAPI starter for a payment gateway service.

## Run locally

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; interactive documentation is at
`/docs`. Start PostgreSQL with `docker compose up -d db` when database-backed
features are added.

## Layout

`app/api` contains HTTP routes, `schemas` request/response contracts, `services`
business logic, `repositories` persistence queries, `models` ORM models, and
`core` shared configuration. Database migrations live in `alembic/`. New ORM
models can inherit from `BaseMixin` for UUID and audit timestamp fields.

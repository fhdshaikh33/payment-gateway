# Database Access & Management Guide

This document provides instructions on connecting to the PostgreSQL database, executing queries, and inspecting tables in the Payment Gateway environment.

---

## 1. Connecting to PostgreSQL Database

### Option 1: Using Docker Compose (Recommended)
Run the following command from the project root directory:
```bash
docker compose exec db psql -U postgres -d payment_gateway
```

### Option 2: Using Docker Exec Directly
```bash
docker exec -it payment_gateway_db psql -U postgres -d payment_gateway
```

---

## 2. Database Configuration Details

| Parameter | Default Value | Environment Variable |
| :--- | :--- | :--- |
| **Host** | `localhost` (or `db` inside Docker network) | `DB_HOST` |
| **Port** | `5432` | `DB_PORT_EXTERNAL` |
| **Database Name** | `payment_gateway` | `DB_NAME` / `POSTGRES_DB` |
| **Username** | `postgres` | `DB_USER` / `POSTGRES_USER` |
| **Password** | `postgres` | `DB_PASSWORD` / `POSTGRES_PASSWORD` |
| **Async URL** | `postgresql+asyncpg://postgres:postgres@localhost:5432/payment_gateway` | `PAYMENT_GATEWAY_DATABASE_URL` |

---

## 3. Useful `psql` Terminal Commands

Inside the `psql` interactive shell:

- `\dt` : List all database tables in current schema.
- `\d users` : Describe schema and constraints of `users` table.
- `\d merchants` : Describe schema of `merchants` table.
- `\d merchant_members` : Describe schema of `merchant_members` table.
- `\d roles` : Describe schema of `roles` table.
- `\l` : List all databases.
- `\q` : Exit the `psql` shell.

---

## 4. Useful SQL Queries

### Inspect Users
```sql
SELECT id, full_name, email, is_platform_admin, is_active, created_at, updated_at 
FROM users;
```

### Inspect Merchants
```sql
SELECT id, business_name, legal_entity_type, kyc_status, created_at, updated_at 
FROM merchants;
```

### Inspect Roles & Members
```sql
SELECT m.business_name, u.email, r.name AS role_name, mm.status
FROM merchant_members mm
JOIN merchants m ON mm.merchant_id = m.id
JOIN users u ON mm.user_id = u.id
LEFT JOIN roles r ON mm.role_id = r.id;
```

---

## 5. Alembic Database Migrations

### Run Migrations to Head
```bash
alembic upgrade head
```

### Check Migration History
```bash
alembic history
```

### Check Current Applied Revision
```bash
alembic current
```

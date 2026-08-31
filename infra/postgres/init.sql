-- Runs once at database creation (mounted into /docker-entrypoint-initdb.d).
-- In CI, the same statements are executed explicitly against the service DB.
-- Everything here is idempotent so it can be re-run safely.

CREATE EXTENSION IF NOT EXISTS vector;

-- Application role: LOGIN, non-superuser, so FORCE ROW LEVEL SECURITY applies to it.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ocr_app') THEN
    CREATE ROLE ocr_app WITH LOGIN PASSWORD 'ocr_app';
  END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE ocr_rag TO ocr_app;
GRANT ALL ON SCHEMA public TO ocr_app;

-- Migrations and the app both connect as ocr_app, so it owns the tables it
-- creates and is still subject to RLS via FORCE ROW LEVEL SECURITY.

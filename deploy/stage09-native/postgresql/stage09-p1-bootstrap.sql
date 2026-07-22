\set ON_ERROR_STOP on
\getenv stage09_p1_database_password STAGE09_P1_DATABASE_PASSWORD

\if :{?stage09_p1_database_password}
\else
\echo 'STAGE09_P1_DATABASE_PASSWORD must be set before bootstrap.'
\quit 1
\endif

SELECT length(:'stage09_p1_database_password') > 0 AS stage09_p1_password_present \gset
\if :stage09_p1_password_present
\else
\echo 'STAGE09_P1_DATABASE_PASSWORD must not be empty.'
\quit 1
\endif

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stage09_p1') THEN
    CREATE ROLE stage09_p1 LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END
$$;

ALTER ROLE stage09_p1 LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
  PASSWORD :'stage09_p1_database_password';

SELECT 'CREATE DATABASE stage09_p1 OWNER stage09_p1'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'stage09_p1')
\gexec

REVOKE ALL ON DATABASE stage09_p1 FROM PUBLIC;
GRANT CONNECT ON DATABASE stage09_p1 TO stage09_p1;

\connect stage09_p1

REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE EXTENSION IF NOT EXISTS vector;

# Architecture decision records

| ADR | Decision |
|---|---|
| [001](001-postgres-storage-psycopg.md) | Tasks are stored in Postgres via psycopg 3 + psycopg_pool; the service owns its schema and creates it idempotently at startup under an advisory lock (no migration tool yet) |

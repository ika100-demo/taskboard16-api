# ADR-001: Postgres storage psycopg

**Status:** Proposed (2026-11-14)

## Context

<!-- why a decision is needed: the forces and constraints -->

## Decision

Tasks are stored in Postgres via psycopg 3 + psycopg_pool; the service owns its schema and creates it idempotently at startup under an advisory lock (no migration tool yet)

## Consequences

<!-- what becomes easier or harder, what a later change must keep -->

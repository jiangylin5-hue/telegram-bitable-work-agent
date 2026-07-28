# Stage09 Real Table Evaluation Inventory — 2026-07-26

## Status

- Result: blocked before import and before provider inference.
- Method: server-side PostgreSQL transaction explicitly set to read-only.
- Retention: no table name, field name, identifier, record value, SQL connection value or model payload was printed or retained.

## Aggregate Inventory

| Measure | Result |
| --- | ---: |
| Active persisted tables | 7 |
| Tables with at least 10 active records | 0 |
| Maximum active records in a single table | 1 |
| Tables passing the real-provider projection gate | 0 |
| Source writes | 0 |
| Imported evaluation records | 0 |
| OpenRouter calls under this protocol | 0 |

The three non-empty tables each had only one active record. The read-only value-shape detector also found a direct-identifier-like pattern in those one-row samples. This is intentionally insufficient for a recall/precision corpus and is not sent to an external provider.

## Decision

No data import, retrieval run or accuracy score is claimed. The next required input is a user-nominated real CSV/XLSX or a permissioned persisted table with at least ten records and an approved visible-field projection. The source is then reconstructed only in an in-memory evaluation workspace; it is not written back to the source PostgreSQL database.

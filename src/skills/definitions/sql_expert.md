# Skill: SQL Expert

## Mission
Analyze, optimize, and execute database queries with a focus on safety and performance.

## Guidelines
- Always inspect the schema using `.schema` or equivalent before writing complex queries.
- Use `EXPLAIN QUERY PLAN` to verify performance for large datasets.
- Prefer read-only operations unless a data modification is explicitly requested.
- When modifying data, always perform a `SELECT` first to verify the target rows.
- Use formatted output mode (e.g., `-header -box` in sqlite3) for better readability.

# Plan 14-3: Web Dashboard & Authentication

## Objective
Provide a read-only visual interface in the browser and secure the API endpoints.

## Tasks
1. **Static Files**: Add support in FastAPI to serve static files from `src/api/static/`.
2. **Dashboard UI**: Create `index.html` and `app.js` in the static directory.
    - Connect to `/ws/events` on load.
    - Render a simple list of active agents and a task log.
3. **Authentication Middleware**: 
    - Implement a simple dependency checking for `X-API-Key` or `Authorization` header.
    - Load valid keys from `config.yaml` or `.env`.
    - Apply this dependency to all `/api/v1/*` routes.

## Verification
- [ ] Navigating to `http://localhost:8000` serves the dashboard.
- [ ] Dashboard updates automatically when agents spawn or finish.
- [ ] Accessing `/api/v1/tasks` without a valid header returns 401 Unauthorized.

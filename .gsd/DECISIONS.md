# DECISIONS.md — Architecture Decision Records

> Log of significant technical decisions.

| # | Date | Decision | Rationale | Status |
|---|------|----------|-----------|--------|
| 1 | 2026-10-17 | React 19 + Vite 8 + Tailwind CSS for frontend | User specified; Vite already scaffolded | Accepted |
| 2 | 2026-10-17 | FastAPI (Python) for backend | User specified; excellent async/WebSocket support | Accepted |
| 3 | 2026-10-17 | PostgreSQL for database | User specified; robust relational DB for healthcare data | Accepted |
| 4 | 2026-10-17 | JWT + bcrypt for auth | Industry standard; httpOnly cookies for security | Accepted |
| 5 | 2026-10-17 | OpenStreetMap + Leaflet for maps | Free, no API key required, user specified | Accepted |
| 6 | 2026-10-17 | scikit-learn + XGBoost for ML | User specified; excellent for tabular prediction tasks | Accepted |
| 7 | 2026-10-17 | Synthetic data only | No real hospital partnerships; all data clearly labeled | Accepted |
| 8 | 2026-10-17 | In-app notifications first, push as stretch | Keeps initial implementation free; Web Push API for later | Accepted |
| 9 | 2026-10-17 | Use local PostgreSQL 18.6 (medismart_db) | User installed locally; Docker Compose dependency removed for now | Accepted |
| 10 | 2026-10-17 | Additive-only migrations with String types | Preserves existing database data; avoids PostgreSQL ENUM migration locks | Accepted |
| 11 | 2026-10-17 | Preserve existing Vite 8 + React 19 frontend | Extend vite.config.js with @tailwindcss/vite; no file re-generation | Accepted |

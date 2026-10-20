# DECISIONS.md — Architecture Decision Records

> Log of significant technical decisions.

| # | Date | Decision | Rationale | Status |
|---|------|----------|-----------|--------|
| 1 | 2026-10-17 | React 19 + Vite 8 + Tailwind CSS for frontend | User specified; Vite already scaffolded | Accepted |
| 2 | 2026-10-17 | FastAPI (Python) for backend | User specified; excellent async/WebSocket support | Accepted |
| 3 | 2026-10-17 | PostgreSQL for database | User specified; robust relational DB for healthcare data | Accepted |
| 4 | 2026-10-17 | JWT + Argon2 for auth | Argon2id is memory-hard, highly resistant to GPU/ASIC attacks; PyJWT for stateless bearer auth | Accepted |
| 5 | 2026-10-17 | OpenStreetMap + Leaflet for maps | Free, no API key required, user specified | Accepted |
| 6 | 2026-10-17 | scikit-learn + XGBoost for ML | User specified; excellent for tabular prediction tasks | Accepted |
| 7 | 2026-10-17 | Synthetic data only | No real hospital partnerships; all data clearly labeled | Accepted |
| 8 | 2026-10-17 | In-app notifications first, push as stretch | Keeps initial implementation free; Web Push API for later | Accepted |
| 9 | 2026-10-17 | Use local PostgreSQL 18.6 (medismart_db) | User installed locally; Docker Compose dependency removed for now | Accepted |
| 10 | 2026-10-17 | Additive-only migrations with String types | Preserves existing database data; avoids PostgreSQL ENUM migration locks | Accepted |
| 11 | 2026-10-17 | Preserve existing Vite 8 + React 19 frontend | Extend vite.config.js with @tailwindcss/vite; no file re-generation | Accepted |
| 29 | 2026-10-20 | Exclude clinical notes from QueueEntryResponse | Eliminates privacy leak in GET /api/v1/queue/my and check-in; retains clinical notes strictly for authorized doctors | Accepted |
| 30 | 2026-10-20 | Additive persistent users.hospital_id affiliation | Sourced authoritatively from PostgreSQL; eliminates header spoofing and stale JWT claims; fails closed | Accepted |
| 31 | 2026-10-20 | Test database isolation via medismart_test_db | Hard security assertion in conftest.py prevents pytest from ever mutating development medismart_db | Accepted |
| 32 | 2026-10-20 | Chronological validation-driven ML pipeline with NonNegativeRegressor wrapper | Prevents temporal lookahead bias; selects winning XGBoost regressor strictly on validation set; guarantees >= 0.0 min wait predictions | Accepted |
| 33 | 2026-10-20 | Imbalanced no-show classification with PR-AUC selection & ThresholdClassifier wrapper | Prioritizes PR-AUC and F1 over deceptive raw accuracy under 23% prevalence; wraps Logistic Regression with validation-calibrated decision threshold | Accepted |
| 34 | 2026-10-20 | Centralized in-memory ML prediction service with Pydantic validation & synthetic disclosure | Avoids repeated disk I/O via thread-safe cached pipelines; guarantees finite non-negative wait times and bounded probabilities; labels risk bands as illustrative; zero DB access | Accepted |


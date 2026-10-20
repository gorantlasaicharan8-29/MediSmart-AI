---
phase: 5
plan: 4
wave: 3
depends_on: [1, 2, 3]
gap_closure: false
---

# Plan 5.4: Doctor Consultation Queue Console

## Objective
Build the client-side **Doctor Consultation Queue Console** in React 19:
1. **Clinical Queue Dashboard**: Doctor-specific queue management interface for authorized doctors, hospital administrators, and system administrators.
2. **Consultation Lifecycle Actions**: Call next patient, call specific patient, complete consultation with clinical notes, skip patient, and recall skipped patient back into the active queue.
3. **Active Patient Workspace**: Dedicated examination view displaying patient name, contact details, scheduled slot time, consultation elapsed timer, and notes input.
4. **Queue Lists & Metrics**: Distinct lists for active waiting patients and skipped patients, paired with live KPI metric cards (Waiting, In Consultation, Completed, Skipped).
5. **Real-Time Synchronization**: Live updates powered by `useQueueSocket` connecting to `/api/v1/queue/ws/{doctorId}` with automatic 10-second REST polling fallback.
6. **Robust Error Handling**: Friendly handling of concurrency conflicts (HTTP 409 when calling a patient while another is in consultation) and network disconnects.

---

## Context
- `backend/app/api/v1/queue.py`: Already implements `GET /doctor/{id}`, `POST /{id}/call`, `POST /{id}/complete`, `POST /{id}/skip`, and `POST /{id}/recall`.
- `backend/app/schemas/queue.py`: `DoctorQueueResponse`, `DoctorQueueItemResponse`, and `QueueActionRequest`.
- `frontend/src/services/api.js`: Queue and doctor API endpoints.
- `frontend/src/hooks/useQueueSocket.js`: Real-time WebSocket hook with exponential backoff and 10s polling fallback.
- `frontend/src/pages/Queue.jsx`: Main queue management page.
- `frontend/src/App.jsx`: Route definitions.
- `frontend/src/context/useAuth.js`: Role and user identity context.

---

## Safety, Security & Architecture Rules

1. **Role-Based Authorization & Cross-Doctor Isolation**:
   - Access restricted to `doctor`, `hospital_admin`, and `system_admin`.
   - Doctors can only view and manage their own queue (`doctor.user_id === user.id`).
   - Hospital admins can only supervise queues of doctors affiliated with their hospital (`doctor.hospital_id === user.hospital_id`).
   - Server-side authorization is strictly enforced by `_verify_doctor_access` on every endpoint. Client-side role checks serve as UX guards, never replacing server validation.
2. **Zero Client JWT Storage**:
   - No JWT tokens in `localStorage` or `sessionStorage`. All requests rely on secure `HttpOnly` browser cookies.
3. **Concurrency Conflict Protection (HTTP 409)**:
   - Calling a patient while another patient is active in consultation returns `409 Conflict` from PostgreSQL advisory locks and row locks.
   - The UI must catch HTTP 409 and display a clear, non-blocking alert ("Another patient is currently in consultation. Please complete or skip the active consultation first.").
4. **Database Non-Destruction**:
   - No database migrations, schema alterations, or table drops.
   - Zero test records left behind; existing records in `medismart_db` remain unmodified.
5. **Strict Scope Control**:
   - Do NOT start Phase 6 (Machine Learning / synthetic predictions).
   - Confined strictly to Plan 5.4 Doctor Queue Console.

---

## Tasks

<task type="auto" effort="low">
  <name>Extend Frontend API Client for Doctor Queue Actions</name>
  <files>
    frontend/src/services/api.js
  </files>
  <action>
    Export helper methods in `frontend/src/services/api.js` wrapping the existing backend queue endpoints:
    1. `getDoctorClinicalQueue(doctorId)`: `GET /api/v1/queue/doctor/${doctorId}`
    2. `callQueuePatient(entryId, notes)`: `POST /api/v1/queue/${entryId}/call` with optional `{ notes }`
    3. `completeQueuePatient(entryId, notes)`: `POST /api/v1/queue/${entryId}/complete` with optional `{ notes }`
    4. `skipQueuePatient(entryId, notes)`: `POST /api/v1/queue/${entryId}/skip` with optional `{ notes }`
    5. `recallQueuePatient(entryId, notes)`: `POST /api/v1/queue/${entryId}/recall` with optional `{ notes }`
  </action>
  <verify>
    npm run lint (in frontend/)
  </verify>
  <done>
    - All 5 doctor queue API methods exported with proper credentials handling
  </done>
</task>

<task type="auto" effort="high">
  <name>Build Doctor Consultation Queue Console Component</name>
  <files>
    frontend/src/components/queue/DoctorQueueConsole.jsx
  </files>
  <action>
    Create `DoctorQueueConsole.jsx`:
    1. **Doctor Identification**:
       - For `doctor`: resolves `Doctor.id` by matching authenticated `user.id` against doctor records via `getDoctors()`.
       - For `hospital_admin`: lists affiliated hospital doctors in a selector dropdown to allow queue supervision.
       - For `system_admin`: allows selecting any doctor across hospitals.
       - For unauthenticated or `patient`: displays access restricted alert card.
    2. **Real-Time Integration (`useQueueSocket`)**:
       - Connects to `/api/v1/queue/ws/{doctorId}`.
       - Automatic 10-second polling fallback if WebSockets disconnect.
       - Connection badge: 🟢 LIVE / 🟡 POLLING / 🔴 RECONNECTING.
       - Immediate sync on events (`PATIENT_CALLED`, `COMPLETED`, `SKIPPED`, `RECALLED`, `CHECKED_IN`, `CANCELLED`).
    3. **Active Patient Workspace (Hero Card)**:
       - Displays patient currently in examination (`status === 'in_consultation'`).
       - Large token display (`Q-003`).
       - Full patient demographics: name, phone, email, scheduled appointment slot time, appointment token reference.
       - Live elapsed timer showing time in consultation (MM:SS).
       - Clinical consultation notes textarea (saved with completion or skip).
       - Actions: "Complete Consultation", "Skip Patient (No-Show)".
       - When no patient is active: prominent "Call Next Patient" banner.
    4. **Waiting Queue List**:
       - Table/cards of waiting patients ordered by position/token.
       - Shows token, position in line (`#1 Next`, `#2`...), patient name, phone, scheduled time.
       - Actions: "Call Patient", "Skip".
    5. **Skipped Patients Tab / Section**:
       - Displays skipped patients with reason/notes.
       - Action: "Recall to Queue" (`POST /{id}/recall`), returning them to waiting queue.
    6. **KPI Metric Summary Cards**:
       - Total Waiting, In Consultation (0 or 1), Total Completed, Total Skipped.
    7. **Feedback & Conflict Handling**:
       - Catch and display 409 Conflict on simultaneous calls with actionable error message.
       - Success toasts/alerts on action completion.
  </action>
  <verify>
    npm run lint (in frontend/)
  </verify>
  <done>
    - Full doctor consultation queue console operational with active workspace, waiting list, skipped list, and KPIs
    - Real-time updates with polling fallback
    - Concurrency conflict handling and patient privacy preserved
  </done>
</task>

<task type="auto" effort="medium">
  <name>Integrate Doctor Console into Queue Page and Route Hierarchy</name>
  <files>
    frontend/src/pages/Queue.jsx
    frontend/src/App.jsx
  </files>
  <action>
    1. In `frontend/src/pages/Queue.jsx`:
       - Add Tab 3: "🩺 Doctor Console".
       - Support deep-linking via query parameters: `?tab=doctor&doctor={doctorId}`.
       - Auto-select "Doctor Console" tab if authenticated user has role `doctor`.
    2. In `frontend/src/App.jsx`:
       - Add dedicated route `/queue/doctor` and `/queue/doctor/:doctorId` for direct doctor console bookmarking.
       - Protect route using existing `<ProtectedRoute>` restricting access to `['doctor', 'hospital_admin', 'system_admin']`.
  </action>
  <verify>
    npm run lint && npm run build (in frontend/)
  </verify>
  <done>
    - Multi-tab Queue page integrates Patient Tracker, Waiting Room Monitor, and Doctor Console
    - Dedicated protected route `/queue/doctor` accessible
  </done>
</task>

<task type="auto" effort="medium">
  <name>Comprehensive Test Suite Verification & Database Integrity Audit</name>
  <files>
    backend/tests/
  </files>
  <action>
    1. Run backend regression suite: `.venv\Scripts\pytest -v` (expecting 93+ passing tests).
    2. Run frontend linter: `npm run lint` (oxlint: 0 errors, 0 warnings).
    3. Run frontend production build: `npm run build` (clean Vite production bundle).
    4. Audit database record counts on `medismart_db`:
       - Confirm hospitals=8, doctors=10, users=10, appointments=0, queue_entries=0.
       - Confirm zero schema alterations, zero migrations executed, zero records altered or deleted.
  </action>
  <verify>
    .venv\Scripts\pytest -v (in backend/)
    npm run lint (in frontend/)
    npm run build (in frontend/)
  </verify>
  <done>
    - 100% backend test pass rate
    - Clean frontend build and linting
    - Database integrity intact
  </done>
</task>

---

## Must-Haves
- [ ] Doctor can view clinical queue with patient demographics, tokens, and positions
- [ ] "Call Next Patient" and "Call Specific Patient" actions functional
- [ ] "Complete Consultation" action with clinical notes functional
- [ ] "Skip Patient" and "Recall Patient" actions functional
- [ ] Elapsed consultation timer active during examination
- [ ] Real-time WebSocket subscriptions with automatic 10-second polling fallback
- [ ] Concurrency 409 Conflict handled gracefully without crashing or UI freeze
- [ ] Cross-doctor access strictly restricted to authorized doctors and hospital admins
- [ ] Zero JWTs stored in localStorage
- [ ] Zero database migrations, schema alterations, or record deletions
- [ ] Clean oxlint (0 errors) and successful Vite production build

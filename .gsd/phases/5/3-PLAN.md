---
phase: 5
plan: 3
wave: 2
depends_on: [1, 2]
gap_closure: false
---

# Plan 5.3: Patient Queue Dashboard, Doctor Queue Controls & Real-Time UX

## Objective
Build the client-side digital queue interface in React 19, including a resilient WebSocket hook with automatic polling fallback, patient live token tracking with countdowns and turn-approaching alerts, an interactive clinic check-in flow, a public waiting-room display board, and a doctor queue console with atomic actions.

## Context
- `frontend/src/pages/Queue.jsx`
- `frontend/src/services/api.js`
- `frontend/src/components/Navbar.jsx`
- `frontend/src/context/useAuth.js`

## Safety & Architecture Rules
1. **Resilient Real-Time Connectivity**:
   - WebSocket client connects to `/api/v1/queue/ws/{doctorId}`.
   - Automatically attempts reconnection on dropped connection with exponential backoff.
   - **Polling Fallback**: If WebSocket connection fails or disconnects persistently, gracefully transitions to periodic HTTP polling (every 10s) without breaking user experience or crashing.
   - Exposes connection status indicator (`🟢 Live Stream` vs `🟡 Polling Mode` vs `🔴 Offline`).
2. **Patient Privacy & PII Protection**:
   - Public queue board displays anonymized tokens (`Token Q-005 • In Consultation • Room 204`) without exposing patient names.
   - Only authenticated patients can view their personal medical details and full appointment tokens.
3. **Role-Enforced Console Access**:
   - Doctor queue management console (Call, Complete, Skip) is only accessible to authenticated doctors and hospital administrators.
4. **Turn-Approaching Alerts**:
   - When a patient's position drops to $\le 2$, trigger prominent visual banners and sound cue alerts so patients don't miss their turn.

## Tasks

<task type="auto" effort="medium">
  <name>Extend API client and build useQueueSocket hook with polling fallback</name>
  <files>
    frontend/src/services/api.js
    frontend/src/hooks/useQueueSocket.js
  </files>
  <action>
    1. Update `frontend/src/services/api.js`:
       - `checkInQueue(data)`: POST `/api/v1/queue/check-in`.
       - `getMyQueueEntry()`: GET `/api/v1/queue/my`.
       - `getDoctorQueue(doctorId)`: GET `/api/v1/queue/doctor/{doctorId}`.
       - `callQueuePatient(entryId)`: POST `/api/v1/queue/{entryId}/call`.
       - `completeQueuePatient(entryId)`: POST `/api/v1/queue/{entryId}/complete`.
       - `skipQueuePatient(entryId, notes)`: POST `/api/v1/queue/{entryId}/skip`.
       - `recallQueuePatient(entryId)`: POST `/api/v1/queue/{entryId}/recall`.
       - `cancelQueueEntry(entryId)`: DELETE `/api/v1/queue/{entryId}`.
    2. Create `frontend/src/hooks/useQueueSocket.js`:
       - Manages WebSocket lifecycle, auto-reconnect, and message handling.
       - Implements 10-second polling fallback if WebSockets fail.
       - Returns `{ queueData, isLive, connectionMode, refresh }`.
  </action>
  <verify>
    npm run lint (in frontend/)
  </verify>
  <done>
    - API client functions ready
    - useQueueSocket hook operational with polling fallback
  </done>
</task>

<task type="auto" effort="high">
  <name>Build Patient Tracker, Public Board, Doctor Console, and Queue Page</name>
  <files>
    frontend/src/components/queue/PatientQueueTracker.jsx
    frontend/src/components/queue/DoctorQueueConsole.jsx
    frontend/src/components/queue/PublicQueueBoard.jsx
    frontend/src/pages/Queue.jsx
  </files>
  <action>
    1. Create `frontend/src/components/queue/PatientQueueTracker.jsx`:
       - Token number badge (`Q-003`).
       - Multi-step progress tracker (Checked In, Waiting, Called, In Consultation, Completed).
       - Dynamic estimated wait time with countdown.
       - "Turn Approaching" visual alert when position <= 2.
    2. Create `frontend/src/components/queue/PublicQueueBoard.jsx`:
       - Waiting-room screen display with high-contrast cards.
       - Currently Serving token + Room.
       - Next Up list and Waiting count.
    3. Create `frontend/src/components/queue/DoctorQueueConsole.jsx`:
       - For doctors/staff: "Currently Examining" with Complete button, "Next Patients" with Call and Skip buttons, and Recalled list.
    4. Update `frontend/src/pages/Queue.jsx`:
       - Multi-tab layout: "My Live Position", "Clinic Check-In", "Live Waiting Board", "Doctor Console".
       - Connects to live API and WebSocket hooks.
  </action>
  <verify>
    npm run lint && npm run build (in frontend/)
  </verify>
  <done>
    - Interactive patient queue tracker with alerts
    - Public display board and doctor management console
    - Clean build with zero lint warnings
  </done>
</task>

## Must-Haves
- [ ] WebSocket client with resilient polling fallback
- [ ] Live queue position and estimated wait time tracking
- [ ] "Turn Approaching" alert for patients at position <= 2
- [ ] Doctor queue controls (Call, Complete, Skip) with row-locked backend safety
- [ ] Public board anonymizes patient PII

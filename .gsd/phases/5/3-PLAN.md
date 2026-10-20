---
phase: 5
plan: 3
wave: 2
depends_on: [1, 2]
gap_closure: false
---

# Plan 5.3: Patient Live Queue Tracker and Waiting Room Monitor Display

## Objective
Build the client-side patient queue tracking and waiting room display interfaces in React 19:
1. **Scope A — Patient Live Queue Tracker**: Live token badge, dynamic queue position, countdown wait time, consultation progress stepper, turn-approaching alert, check-in flow, and cancellation.
2. **Scope B — Waiting Room Monitor Display**: High-contrast, large-font full-screen monitor display for waiting rooms showing current consultation token, upcoming tokens, zero-PII privacy guarantee, audio/visual pulse on call, and doctor selection.
3. **Resilient Real-Time Engine**: WebSocket connection hook (`useQueueSocket`) with automatic reconnection and a 10-second periodic REST polling fallback.

## Context
- `frontend/src/pages/Queue.jsx`
- `frontend/src/services/api.js`
- `frontend/src/hooks/useQueueSocket.js`
- `frontend/src/components/queue/PatientQueueTracker.jsx`
- `frontend/src/components/queue/WaitingRoomMonitor.jsx`
- `frontend/src/components/Navbar.jsx`
- `frontend/src/context/useAuth.js`

## Safety & Architecture Rules
1. **Scope Boundary**: Implement Scope A (Patient Live Queue Tracker) and Scope B (Waiting Room Monitor) ONLY. Do not start Plan 5.4 (Doctor Queue Console).
2. **Zero PII in Waiting Room Display**: The public waiting room display must never render patient names, emails, phone numbers, UUIDs, or clinical notes.
3. **Resilient Connectivity**:
   - WebSocket client connects to `/api/v1/queue/ws/{doctorId}`.
   - Reconnection with exponential backoff on drop.
   - Automatic 10-second polling fallback if WebSockets fail or disconnect.
   - Visual connection indicator (`Live Connection`, `Polling Mode`, `Offline`).
4. **Turn-Approaching Alert**: Visual alert banner and Web Audio chime when position $\le 2$.
5. **No LocalStorage JWTs**: Retain HttpOnly cookie authentication.

## Tasks

<task type="auto" effort="medium">
  <name>Extend API Client and Build useQueueSocket Hook with Polling Fallback</name>
  <files>
    frontend/src/services/api.js
    frontend/src/hooks/useQueueSocket.js
    frontend/vite.config.js
  </files>
  <action>
    1. Add Queue API functions in `frontend/src/services/api.js`:
       - `checkInQueue({ appointment_token, appointment_id })`: POST `/api/v1/queue/check-in`
       - `getMyQueueEntry()`: GET `/api/v1/queue/my`
       - `getDoctorPublicBoard(doctorId)`: GET `/api/v1/queue/doctor/${doctorId}/public-board`
       - `cancelQueueEntry(entryId)`: DELETE `/api/v1/queue/${entryId}`
    2. Ensure `frontend/vite.config.js` enables `ws: true` for the `/api` proxy.
    3. Create `frontend/src/hooks/useQueueSocket.js`:
       - Manages WebSocket lifecycle to `/api/v1/queue/ws/{doctorId}`.
       - Implements auto-reconnect with exponential backoff.
       - Implements automatic 10-second polling fallback via provided fetcher function.
       - Returns `{ data, isLive, connectionMode, lastRefreshed, refresh, error }`.
  </action>
  <verify>
    npm run lint (in frontend/)
  </verify>
  <done>
    - API client functions for check-in, my queue, public board, and queue cancellation
    - useQueueSocket hook with dual transport (WebSocket + 10s polling fallback)
  </done>
</task>

<task type="auto" effort="high">
  <name>Build Patient Live Queue Tracker Component (Scope A)</name>
  <files>
    frontend/src/components/queue/PatientQueueTracker.jsx
    frontend/src/utils/sound.js
  </files>
  <action>
    1. Create Web Audio chime utility in `frontend/src/utils/sound.js` using browser AudioContext (no external assets).
    2. Create `frontend/src/components/queue/PatientQueueTracker.jsx`:
       - Displays authenticated patient's active queue entry today.
       - High-visibility token badge (`Q-003`).
       - Dynamic position indicator (`Position 2 in Line` or `In Consultation`).
       - Estimated wait time countdown.
       - Multi-step progress tracker: Checked In -> Waiting in Line -> In Consultation -> Completed.
       - "Turn Approaching" visual alert when position <= 2.
       - "Cancel Queue Entry" button with confirmation dialog.
       - Interactive check-in card when patient has no active queue entry today.
       - Handles loading, empty, error, and reconnecting states.
  </action>
  <verify>
    npm run lint (in frontend/)
  </verify>
  <done>
    - Patient Live Queue Tracker operational with privacy, progress, and alerts
  </done>
</task>

<task type="auto" effort="high">
  <name>Build Full-Screen Waiting Room Monitor Display & Queue Page (Scope B)</name>
  <files>
    frontend/src/components/queue/WaitingRoomMonitor.jsx
    frontend/src/pages/Queue.jsx
    frontend/src/App.jsx
  </files>
  <action>
    1. Create `frontend/src/components/queue/WaitingRoomMonitor.jsx`:
       - High-contrast, large-font display optimized for waiting-room TV/wall monitors.
       - Prominent "Currently Serving" card with token number (`Q-004`), status, doctor name, and room.
       - Upcoming tokens grid showing token display, position, and estimated wait times.
       - Total waiting count badge.
       - Audio chime and pulse animation when new patient is called.
       - Fullscreen toggle via standard browser Fullscreen API.
       - Doctor selector dropdown to switch clinics easily.
       - Strict zero PII guarantee: no patient names, phone numbers, emails, or notes rendered.
    2. Update `frontend/src/pages/Queue.jsx`:
       - Integrated tabbed navigation: "My Queue Status" (Patient Tracker), "Waiting Room Monitor" (Public Board), "Clinic Check-In".
    3. Update `frontend/src/App.jsx`:
       - Add dedicated standalone route `/queue/monitor/:doctorId` for direct kiosk/TV display.
  </action>
  <verify>
    npm run lint && npm run build (in frontend/)
  </verify>
  <done>
    - Full-screen Waiting Room Monitor with zero PII and large-font TV design
    - Multi-tab Queue page and dedicated monitor route
    - Clean oxlint (0 errors) and Vite production build
  </done>
</task>

## Must-Haves
- [ ] Live queue position and estimated wait time tracking for authenticated patients
- [ ] Turn-approaching alert for patients with position <= 2
- [ ] Zero-PII public waiting room monitor display with large-format typography
- [ ] WebSocket real-time subscription with resilient 10-second polling fallback
- [ ] Clean empty, loading, error, and reconnecting states
- [ ] Clean oxlint and Vite production build with zero warnings

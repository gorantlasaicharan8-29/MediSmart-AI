---
phase: 4
plan: 3
wave: 2
depends_on: [1, 2]
gap_closure: false
---

# Plan 4.3: Frontend Doctor Directory, Slot Booking Modal & Appointment Management

## Objective
Build the client-side doctor discovery and appointment booking interface in React 19, including doctor search and filtering, credential provenance badges, hospital-affiliated doctor cards, dynamic slot selection calendar, secure booking modal with conflict handling, unique token confirmation, and an appointment history tracking view.

## Context
- `frontend/src/pages/Doctors.jsx`
- `frontend/src/pages/Appointments.jsx`
- `frontend/src/services/api.js`
- `frontend/src/components/Navbar.jsx`
- `frontend/src/App.jsx`

## Security & Architecture Rules
1. **Interactive Slot Booking & Conflict UX**:
   - Date picker restricts selection to present and future dates (`min = today`).
   - Dynamically loads slots from `/doctors/{id}/slots?date=...` and disables occupied slots.
   - If a 409 Conflict occurs due to concurrent booking, display a prominent warning: *"This time slot has just been reserved by another patient. Please choose another available slot."*
2. **Credential Provenance Badges**:
   - Visually distinguish doctor credentials:
     - `Verified Specialist`: Emerald badge (`✓ Verified Specialist`).
     - `Sample Profile`: Amber badge (`⚠️ Demo Profile`).
3. **Tracking Token Visibility**:
   - Prominently display the unique tracking token (`MS-YYYYMMDD-XXXX`) upon booking with copy action and link to appointments dashboard.
4. **Patient Confidentiality & Cancellation**:
   - Patient appointment history view shows only the logged-in user's records.
   - Cancellation modal allows entering an optional cancellation reason.
5. **Preserved Design System**:
   - Warm healthcare aesthetic (teal/cyan accents, slate typography, rounded-2xl cards, micro-animations).

## Tasks

<task type="auto" effort="medium">
  <name>Extend API client and build doctor directory with credential badges</name>
  <files>
    frontend/src/services/api.js
    frontend/src/components/doctors/DoctorCard.jsx
    frontend/src/components/doctors/DoctorFilters.jsx
    frontend/src/pages/Doctors.jsx
  </files>
  <action>
    1. Update `frontend/src/services/api.js`:
       - `getDoctors(params)`: GET `/api/v1/doctors`.
       - `getDoctorById(id)`: GET `/api/v1/doctors/{id}`.
       - `getDoctorSlots(doctorId, date)`: GET `/api/v1/doctors/{doctorId}/slots`.
       - `bookAppointment(data)`: POST `/api/v1/appointments`.
       - `getMyAppointments(params)`: GET `/api/v1/appointments`.
       - `cancelAppointment(id, reason)`: POST `/api/v1/appointments/{id}/cancel`.
    2. Create `frontend/src/components/doctors/DoctorCard.jsx`:
       - Shows doctor name, qualification, specialty badge, experience, consultation fee, hospital affiliation, `credential_status` badge, and "Book Consultation" button.
    3. Create `frontend/src/components/doctors/DoctorFilters.jsx`:
       - Search input (debounced), specialty filter pills, hospital dropdown, availability toggle.
    4. Update `frontend/src/pages/Doctors.jsx`:
       - Connects doctor directory with live API queries and filter controls.
  </action>
  <verify>
    npm run lint && npm run build (in frontend/)
  </verify>
  <done>
    - Doctor API client functions ready
    - Doctor directory and filters operational
    - Credential status badges displayed
  </done>
</task>

<task type="auto" effort="medium">
  <name>Implement BookingModal, Appointments page, and Navbar integration</name>
  <files>
    frontend/src/components/appointments/BookingModal.jsx
    frontend/src/components/appointments/AppointmentCard.jsx
    frontend/src/pages/Appointments.jsx
    frontend/src/components/Navbar.jsx
    frontend/src/App.jsx
  </files>
  <action>
    1. Create `frontend/src/components/appointments/BookingModal.jsx`:
       - Date picker (min = today).
       - Fetches doctor slots dynamically on date change.
       - Grid of 30-min slot buttons; booked slots disabled and labeled "Occupied".
       - Notes textarea.
       - Handles 409 conflict safely.
       - Displays confirmed booking token (`MS-YYYYMMDD-XXXX`) with copy button.
    2. Create `frontend/src/components/appointments/AppointmentCard.jsx`:
       - Displays token badge, doctor name, hospital, date, time, status badge (`Scheduled`, `Cancelled`), and cancel trigger.
    3. Create `frontend/src/pages/Appointments.jsx`:
       - Patient appointment dashboard with active upcoming and past appointments.
       - Cancellation confirmation dialog with optional reason.
    4. Register `/appointments` route in `frontend/src/App.jsx` wrapped in `ProtectedRoute`.
    5. Add "Appointments" navigation link in `frontend/src/components/Navbar.jsx` for authenticated users.
  </action>
  <verify>
    npm run lint && npm run build (in frontend/)
  </verify>
  <done>
    - Booking modal operational with real-time slot availability
    - Appointment tracking and cancellation verified
    - Zero lint errors and clean build
  </done>
</task>

## Must-Haves
- [ ] Credential status badge displayed on doctor cards
- [ ] Available slots computed dynamically from doctor schedule
- [ ] 409 conflict handled gracefully in UI
- [ ] Unique appointment token displayed upon booking
- [ ] Patient appointment history and cancellation functional

---
phase: 3
plan: 3
wave: 2
depends_on: [1, 2]
gap_closure: false
---

# Plan 3.3: Frontend Interactive Leaflet Map & Hospital Discovery Directory

## Objective
Implement the interactive Leaflet + OpenStreetMap hospital discovery interface in React 19, featuring map markers with medical popup cards, search and multi-facet filtering, responsive split-screen list/map layout, graceful handling of facilities with missing coordinates, data provenance badges, and admin facility creation controls.

## Context
- `frontend/src/pages/Hospitals.jsx`
- `frontend/src/services/api.js`
- `frontend/src/context/useAuth.js`
- React 19 + Vite 8 + Tailwind CSS v4

## Security & Architecture Rules
1. **OpenStreetMap Attribution & Usage Policy Compliance**:
   - The tile layer must render mandatory OpenStreetMap attribution:
     `&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors`
   - Use standard public tile servers with standard User-Agent and caching headers without excessive hammering.
2. **Safe Handling of Incomplete Information**:
   - Hospitals with missing coordinates (`latitude === null || longitude === null`) must never cause React Leaflet or map rendering to crash.
   - Display unmapped hospitals in the directory list with a clear "GPS Location Pending" badge and provide an unmapped facilities drawer/tab.
3. **Data Provenance Badges**:
   - Visually distinguish records:
     - `Verified`: Emerald badge (validated physical facility).
     - `OSM Import`: Cyan/Teal badge (imported from OpenStreetMap).
     - `Sample Data`: Amber badge (demonstration/test facility).
4. **Preserved Design System**:
   - Maintain the warm healthcare aesthetic (teal/cyan accents, slate typography, rounded-2xl cards, subtle micro-interactions).
   - Ensure responsive layout works on mobile and desktop.

## Tasks

<task type="auto" effort="medium">
  <name>Install Leaflet dependencies and configure Leaflet asset loader</name>
  <files>
    frontend/package.json
    frontend/src/components/map/leafletConfig.js
    frontend/src/services/api.js
  </files>
  <action>
    1. Install `leaflet` and `react-leaflet` in `frontend/`.
    2. Create `frontend/src/components/map/leafletConfig.js`:
       - Resolve default Leaflet marker icon asset paths in Vite to avoid missing icon 404s.
       - Provide custom SVG medical pin markers styled with MediSmart theme colors.
    3. Update `frontend/src/services/api.js`:
       - Add `getHospitals(params)`: calls `GET /api/v1/hospitals`.
       - Add `getHospitalById(id)`: calls `GET /api/v1/hospitals/{id}`.
       - Add `createHospital(data)`: calls `POST /api/v1/hospitals`.
       - Add `updateHospital(id, data)`: calls `PUT /api/v1/hospitals/{id}`.
  </action>
  <verify>
    npm run build (in frontend/)
  </verify>
  <done>
    - Leaflet & react-leaflet installed and building without errors
    - Icon resolution configured
    - API client functions ready
  </done>
</task>

<task type="auto" effort="medium">
  <name>Build interactive Map, Hospital Card, Filters, and Admin Creation Modal</name>
  <files>
    frontend/src/components/map/HospitalMap.jsx
    frontend/src/components/hospitals/HospitalCard.jsx
    frontend/src/components/hospitals/HospitalFilters.jsx
    frontend/src/components/hospitals/HospitalDetailModal.jsx
    frontend/src/components/hospitals/CreateHospitalModal.jsx
    frontend/src/pages/Hospitals.jsx
  </files>
  <action>
    1. Create `frontend/src/components/map/HospitalMap.jsx`:
       - `MapContainer` with OSM `TileLayer` and mandatory copyright attribution.
       - Render markers for all mapped hospitals.
       - Marker click opens popup with facility details, specialties, and "View Details" trigger.
       - Smooth pan/zoom to selected hospital from directory cards.
    2. Create `frontend/src/components/hospitals/HospitalCard.jsx`:
       - Displays name, address, city, state, contact info, specialty tags, facilities.
       - Shows `Verified` / `OSM Import` / `Sample Data` provenance badge.
       - Shows `📍 Mapped` or `⚠️ GPS Pending` badge.
    3. Create `frontend/src/components/hospitals/HospitalFilters.jsx`:
       - Search bar (debounced).
       - City dropdown selector populated dynamically from hospital data.
       - Specialty multi-select pills (Cardiology, Orthopedics, Emergency, etc.).
       - Toggle for "Mapped facilities only".
    4. Create `frontend/src/components/hospitals/HospitalDetailModal.jsx`:
       - Modal displaying full profile, specialties, facilities, contact channels, coordinates, and OSM attribution.
    5. Create `frontend/src/components/hospitals/CreateHospitalModal.jsx`:
       - Form for `hospital_admin` and `system_admin` users to add new facilities.
    6. Refactor `frontend/src/pages/Hospitals.jsx`:
       - Responsive two-column layout (Directory list on left, interactive sticky map on right on desktop; tab toggle on mobile).
       - Live query synchronization.
  </action>
  <verify>
    npm run lint && npm run build (in frontend/)
  </verify>
  <done>
    - Interactive OpenStreetMap operational with marker popups
    - Filter and search working smoothly
    - Missing coordinates handled without errors
    - Responsive layout verified
    - Zero lint warnings
  </done>
</task>

## Must-Haves
- [ ] React Leaflet map with OpenStreetMap tiles and proper copyright attribution
- [ ] Visual markers for hospitals with popup information
- [ ] Search and multi-criteria filters (search, city, specialty, mapped status)
- [ ] Graceful handling of facilities lacking coordinates
- [ ] Visual data provenance badges (Verified vs Sample)
- [ ] Clean Vite build and 0 lint warnings

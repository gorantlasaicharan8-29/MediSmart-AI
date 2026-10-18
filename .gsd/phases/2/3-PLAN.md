---
phase: 2
plan: 3
wave: 2
depends_on: [1, 2]
gap_closure: false
---

# Plan 2.3: Frontend Auth State, Connected Pages & Protected Routes

## Objective
Connect the existing React 19 Login and Register pages to the FastAPI backend, introduce client-side authentication state management (`AuthContext`), handle duplicate email error feedback cleanly, and implement role-aware protected route wrappers.

## Context
- `frontend/src/pages/Login.jsx` (existing login mockup)
- `frontend/src/pages/Register.jsx` (existing register mockup)
- `frontend/src/components/Navbar.jsx` (navbar with auth links)
- `frontend/src/services/api.js` (existing API client)
- `frontend/src/App.jsx` (route definitions)

## Tasks

<task type="auto" effort="medium">
  <name>Create AuthContext and wire API authentication client</name>
  <files>
    frontend/src/context/AuthContext.jsx
    frontend/src/services/api.js
    frontend/src/components/ProtectedRoute.jsx
  </files>
  <action>
    1. Update `frontend/src/services/api.js`:
       - Add `registerUser(userData)` -> `POST /api/v1/auth/register`
       - Add `loginUser(credentials)` -> `POST /api/v1/auth/login`
       - Add `getCurrentUser(token)` -> `GET /api/v1/auth/me` with `Authorization: Bearer <token>`
       - Add token retrieval helper (`getStoredToken`, `setStoredToken`, `clearStoredToken`).
    2. Create `frontend/src/context/AuthContext.jsx`:
       - Provides `user`, `token`, `isAuthenticated`, `isLoading`, `login`, `register`, `logout`
       - On mount, checks for stored token in `localStorage` and validates with `getCurrentUser`
       - Exports `useAuth` hook for components.
    3. Create `frontend/src/components/ProtectedRoute.jsx`:
       - Checks `isLoading`; renders subtle loading skeleton while checking token
       - If not authenticated, redirects to `/login` with `state: { from: location }`
       - If `allowedRoles` is specified and `user.role` is not in `allowedRoles`, renders access denied message or redirects.
  </action>
  <verify>
    npm run build (in frontend/)
  </verify>
  <done>
    - AuthContext and useAuth created
    - ProtectedRoute component created
  </done>
</task>

<task type="auto" effort="medium">
  <name>Connect Login, Register, and Navbar to live auth state</name>
  <files>
    frontend/src/pages/Login.jsx
    frontend/src/pages/Register.jsx
    frontend/src/components/Navbar.jsx
    frontend/src/App.jsx
  </files>
  <action>
    1. Update `frontend/src/pages/Register.jsx`:
       - Connect form submission to `registerUser`
       - Display clear loading spinner during request
       - If backend returns 409 Conflict, display: "An account with this email address is already registered. Please sign in or use a different email."
       - On success, redirect to `/login` with success banner.
    2. Update `frontend/src/pages/Login.jsx`:
       - Connect form submission to `loginUser`
       - Display error banner if backend returns 401 Unauthorized ("Invalid email or password")
       - On success, save token via `AuthContext` and navigate to destination route.
    3. Update `frontend/src/components/Navbar.jsx`:
       - Use `useAuth`
       - If authenticated: display user full name, role badge (e.g. `Patient`, `Doctor`), and Sign Out button
       - If unauthenticated: display existing "Sign In" and "Register" buttons.
    4. Wrap application in `AuthProvider` in `frontend/src/App.jsx`.
  </action>
  <verify>
    npm run lint && npm run build (in frontend/)
  </verify>
  <done>
    - Register and Login connected to live backend APIs
    - Duplicate emails handled safely with clear UI feedback
    - Navbar updates dynamically based on authentication state
  </done>
</task>

## Must-Haves
- [ ] Existing Vite 8 + React 19 setup and Tailwind v4 preserved
- [ ] Duplicate email errors handled gracefully without breaking
- [ ] Protected routes block unauthorized roles
- [ ] No secrets stored in Git

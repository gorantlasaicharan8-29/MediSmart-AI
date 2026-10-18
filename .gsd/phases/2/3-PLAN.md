---
phase: 2
plan: 3
wave: 2
depends_on: [1, 2]
gap_closure: false
---

# Plan 2.3: Frontend Auth State, Connected Pages & Protected Routes

## Objective
Connect React 19 Login and Register pages to backend endpoints using secure browser authentication (`credentials: 'include'` for HttpOnly cookies, avoiding long-lived tokens in localStorage), provide clear UI feedback for duplicate emails and generic login errors, and enforce client-side protected route guards with role checks.

## Context
- `frontend/src/pages/Login.jsx`
- `frontend/src/pages/Register.jsx`
- `frontend/src/components/Navbar.jsx`
- `frontend/src/services/api.js`
- `frontend/src/App.jsx`

## Security & Architecture Rules
1. **Browser Authentication Strategy**:
   - Prefer `HttpOnly`, `SameSite=Lax` cookies for browser authentication.
   - All frontend API calls use `credentials: 'include'`.
   - Avoid storing long-lived JWT access tokens in `localStorage` to eliminate XSS token theft vectors.
   - On app startup, `AuthContext` calls `GET /api/v1/auth/me` (with `credentials: 'include'`) to restore the session and populate user state.
2. **Controlled Registration UI**:
   - `Register.jsx` allows self-registration for `Patient` and `Doctor`.
   - Administrative roles display an informative callout: *"Hospital Admin and System Admin accounts are provisioned directly by administrative staff."*
3. **Accurate Logout Behavior**:
   - Logout calls `POST /api/v1/auth/logout` (server clears the `HttpOnly` cookie), resets React state, and navigates to `/login`.
   - Accurately communicated as session termination and cookie clearing.
4. **Preserved Design & Assets**:
   - All existing Tailwind v4 styles, warm background palette, components, and layout shells are preserved.

## Tasks

<task type="auto" effort="medium">
  <name>Implement API auth client and AuthContext with cookie session verification</name>
  <files>
    frontend/src/services/api.js
    frontend/src/context/AuthContext.jsx
    frontend/src/components/ProtectedRoute.jsx
  </files>
  <action>
    1. Update `frontend/src/services/api.js`:
       - Configure standard fetch wrapper using `credentials: 'include'`.
       - `registerUser(payload)`: POST `/api/v1/auth/register`.
       - `loginUser(payload)`: POST `/api/v1/auth/login`.
       - `getCurrentUser()`: GET `/api/v1/auth/me`.
       - `logoutUser()`: POST `/api/v1/auth/logout`.
    2. Create `frontend/src/context/AuthContext.jsx`:
       - `user`, `isAuthenticated`, `isLoading`, `login`, `register`, `logout`.
       - `useEffect` on mount queries `getCurrentUser()` with `credentials: 'include'` to restore session if cookie is present.
       - Clean error handling (if 401, sets `user=null`).
    3. Create `frontend/src/components/ProtectedRoute.jsx`:
       - Shows subtle loading state while `isLoading` is true.
       - If not authenticated, redirects to `/login`.
       - If `allowedRoles` specified and `user.role` not in `allowedRoles`, renders clean Access Denied message with button to return to authorized area.
  </action>
  <verify>
    npm run build (in frontend/)
  </verify>
  <done>
    - api.js uses credentials: 'include'
    - AuthContext manages session without long-lived tokens in localStorage
    - ProtectedRoute enforces client-side route access
  </done>
</task>

<task type="auto" effort="medium">
  <name>Connect Login, Register, and Navbar to live authentication</name>
  <files>
    frontend/src/pages/Login.jsx
    frontend/src/pages/Register.jsx
    frontend/src/components/Navbar.jsx
    frontend/src/App.jsx
  </files>
  <action>
    1. Update `frontend/src/pages/Login.jsx`:
       - Wire form to `login(email, password)`.
       - On 401 error, display generic alert: *"Invalid email or password"*.
       - On success, redirect to destination.
    2. Update `frontend/src/pages/Register.jsx`:
       - Restrict public role selector to `patient` and `doctor`.
       - On 409 error, display banner: *"An account with this email address already exists. Please sign in or use another email."*
       - On success, redirect to `/login` with success banner.
    3. Update `frontend/src/components/Navbar.jsx`:
       - Consume `useAuth()`.
       - If authenticated: show user's name, role badge, and Sign Out button.
       - If unauthenticated: show Sign In and Register links.
    4. Wrap application in `AuthProvider` in `frontend/src/App.jsx`.
  </action>
  <verify>
    npm run lint && npm run build (in frontend/)
  </verify>
  <done>
    - Login and Register live and verified
    - Duplicate email handling verified
    - Navbar reflects live auth state
    - Zero lint warnings and clean build
  </done>
</task>

## Must-Haves
- [ ] HttpOnly cookie transport used without long-lived token storage in localStorage
- [ ] Safe generic error messages on login
- [ ] Duplicate email error handled cleanly with 409
- [ ] Existing UI design, Tailwind v4, and React 19 preserved

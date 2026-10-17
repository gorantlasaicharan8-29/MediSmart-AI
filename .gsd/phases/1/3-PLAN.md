---
phase: 1
plan: 3
wave: 1
gap_closure: false
---

# Plan 1.3: Frontend — Tailwind CSS, Routing & Layout Shell

## Objective
Configure the existing Vite React frontend with Tailwind CSS, install react-router-dom, and create the application layout shell with navigation — transforming the boilerplate into the MediSmart app structure.

## Context
Load these files for context:
- .gsd/SPEC.md (Technology Stack, Users section)
- frontend/package.json
- frontend/src/main.jsx
- frontend/vite.config.js

## Tasks

<task type="auto" effort="medium">
  <name>Install Tailwind CSS and configure with Vite</name>
  <files>
    frontend/package.json
    frontend/src/index.css
    frontend/tailwind.config.js
    frontend/postcss.config.js
  </files>
  <action>
    1. Install dependencies:
       npm install -D tailwindcss @tailwindcss/vite
       npm install react-router-dom axios

    2. Update vite.config.js to add the Tailwind CSS Vite plugin:
       ```js
       import tailwindcss from '@tailwindcss/vite'
       // add tailwindcss() to plugins array
       ```

    3. Replace frontend/src/index.css content with:
       ```css
       @import "tailwindcss";
       ```
       (Tailwind v4 uses CSS-first configuration with @import)

    4. Remove frontend/src/App.css (Tailwind replaces it)

    5. Clean up App.jsx:
       - Remove the import of App.css
       - Remove the Vite boilerplate content
       - Replace with a simple placeholder: <div className="min-h-screen bg-gray-50"><h1 className="text-3xl font-bold text-center pt-20">MediSmart</h1></div>

    AVOID: Installing Tailwind v3 config pattern — Vite 8 + Tailwind v4 uses the @tailwindcss/vite plugin
    AVOID: Creating tailwind.config.js — Tailwind v4 uses CSS-first configuration
    USE: @tailwindcss/vite plugin (not postcss-based setup)
  </action>
  <verify>
    cd frontend
    npm run build
  </verify>
  <done>
    - `npm run build` completes without errors
    - Tailwind utility classes are functional in output CSS
    - No App.css file remains
  </done>
</task>

<task type="auto" effort="medium">
  <name>Create routing and layout shell</name>
  <files>
    frontend/src/main.jsx
    frontend/src/App.jsx
    frontend/src/layouts/MainLayout.jsx
    frontend/src/pages/Home.jsx
    frontend/src/pages/Login.jsx
    frontend/src/pages/Register.jsx
    frontend/src/pages/NotFound.jsx
    frontend/src/components/Navbar.jsx
    frontend/src/components/Footer.jsx
  </files>
  <action>
    1. Create `frontend/src/layouts/MainLayout.jsx`:
       - Sticky top navigation bar (Navbar component)
       - Main content area with <Outlet />
       - Footer component
       - Uses Tailwind classes for clean, modern layout

    2. Create `frontend/src/components/Navbar.jsx`:
       - MediSmart logo/brand text (left)
       - Navigation links: Home, Hospitals, Doctors (center)
       - Auth buttons: Login, Register (right) — or user menu when logged in (placeholder for Phase 2)
       - Responsive: hamburger menu on mobile
       - Sticky positioning with subtle shadow

    3. Create `frontend/src/components/Footer.jsx`:
       - Simple footer with copyright, links
       - Tailwind styled, dark background

    4. Create placeholder pages (just shells with heading + layout):
       - `pages/Home.jsx` — Hero section with "Find Hospitals Near You" heading, search bar placeholder
       - `pages/Login.jsx` — "Login" heading
       - `pages/Register.jsx` — "Register" heading
       - `pages/NotFound.jsx` — 404 page

    5. Update `frontend/src/App.jsx`:
       - Import BrowserRouter, Routes, Route from react-router-dom
       - Define routes:
         / → MainLayout → Home
         /login → MainLayout → Login
         /register → MainLayout → Register
         * → MainLayout → NotFound

    6. Update `frontend/src/main.jsx`:
       - Wrap App in BrowserRouter

    AVOID: Importing App.css or any non-existent CSS files
    AVOID: Creating complex page content — these are shells for Phase 2+
    USE: Tailwind utility classes for all styling
    USE: React Router v6+ pattern with layout routes
  </action>
  <verify>
    cd frontend
    npm run build
  </verify>
  <done>
    - Build succeeds with no errors
    - 4 routes defined (/, /login, /register, /*)
    - Navbar renders with navigation links
    - Layout wraps all pages with consistent header/footer
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] Tailwind CSS classes compile and appear in build output
- [ ] React Router navigates between pages without full reload
- [ ] Layout shell renders Navbar + content + Footer on every page
- [ ] `npm run build` produces no errors or warnings

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] Frontend ready for feature development in Phase 2+

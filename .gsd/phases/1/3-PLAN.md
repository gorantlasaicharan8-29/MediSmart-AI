---
phase: 1
plan: 3
wave: 1
gap_closure: false
---

# Plan 1.3: Frontend — Tailwind CSS v4, Routing & Layout Shell (Preserve Existing Setup)

## Objective
Add Tailwind CSS v4 and react-router-dom to the existing Vite React frontend WITHOUT breaking the current setup. Preserve all existing files — only add new files and make minimal, targeted changes to existing ones.

## Context
Load these files for context:
- .gsd/SPEC.md (Technology Stack, Users section)
- frontend/package.json (existing dependencies: React 19, Vite 8)
- frontend/src/main.jsx (existing entry point)
- frontend/vite.config.js (existing config — must be extended, not replaced)
- frontend/src/App.jsx (existing boilerplate — will be updated, not deleted)

## Tasks

<task type="auto" effort="medium">
  <name>Install Tailwind CSS v4 and React Router without breaking Vite</name>
  <files>
    frontend/package.json
    frontend/vite.config.js
    frontend/src/index.css
  </files>
  <action>
    1. Install dependencies (additive only — do NOT remove existing packages):
       cd frontend
       npm install -D tailwindcss @tailwindcss/vite
       npm install react-router-dom axios

    2. Update frontend/vite.config.js — ADD the Tailwind plugin to the existing config:
       ```js
       import tailwindcss from '@tailwindcss/vite'
       import react from '@vitejs/plugin-react'
       import { defineConfig } from 'vite'

       export default defineConfig({
         plugins: [react(), tailwindcss()],
       })
       ```
       IMPORTANT: Keep the existing react() plugin. Only ADD tailwindcss().

    3. Update frontend/src/index.css — Replace content with Tailwind v4 import:
       ```css
       @import "tailwindcss";
       ```
       The existing index.css contains only Vite default styles that will be replaced
       by Tailwind utilities. This is safe.

    4. Do NOT delete any existing files (App.css, assets/, etc.) at this step.
       App.css will be cleaned up only after App.jsx is updated in the next task.

    AVOID: Deleting or overwriting vite.config.js entirely — extend it
    AVOID: Installing Tailwind v3 patterns (postcss.config.js, tailwind.config.js)
    AVOID: Removing any existing dependencies from package.json
    USE: @tailwindcss/vite plugin (Tailwind v4 + Vite 8 pattern)
    USE: @import "tailwindcss" in CSS (v4 CSS-first configuration)
  </action>
  <verify>
    cd frontend
    npm run build
  </verify>
  <done>
    - `npm run build` succeeds without errors
    - Tailwind CSS v4 is installed and configured
    - react-router-dom and axios are installed
    - Existing vite.config.js is extended (not replaced)
    - All existing files still present
  </done>
</task>

<task type="auto" effort="medium">
  <name>Create routing and layout shell (preserve existing structure)</name>
  <files>
    frontend/src/App.jsx
    frontend/src/main.jsx
    frontend/src/layouts/MainLayout.jsx
    frontend/src/pages/Home.jsx
    frontend/src/pages/Login.jsx
    frontend/src/pages/Register.jsx
    frontend/src/pages/NotFound.jsx
    frontend/src/components/Navbar.jsx
    frontend/src/components/Footer.jsx
  </files>
  <action>
    1. Create NEW directories and files (all new — no overwrites):
       - frontend/src/layouts/
       - frontend/src/pages/
       - frontend/src/components/

    2. Create `frontend/src/components/Navbar.jsx`:
       - MediSmart brand text (left side)
       - Navigation links: Home, Hospitals, Doctors (center)
       - Auth placeholder links: Login, Register (right side)
       - Responsive: hamburger menu on mobile (use useState for toggle)
       - Tailwind classes: sticky top, white bg, subtle shadow, z-50

    3. Create `frontend/src/components/Footer.jsx`:
       - Copyright line: "© 2026 MediSmart. All rights reserved."
       - Simple links: About, Contact, Privacy
       - Tailwind: dark background (slate-800), light text, padding

    4. Create `frontend/src/layouts/MainLayout.jsx`:
       - Import Navbar and Footer
       - Render: Navbar → <main><Outlet /></main> → Footer
       - Tailwind: min-h-screen flex flex-col, main grows with flex-1

    5. Create placeholder pages (shells with Tailwind styling):
       - `pages/Home.jsx`:
         Hero section: "Smart Hospital Discovery" heading
         Subtitle: "Find hospitals, book appointments, track your queue"
         Centered layout with gradient background
       - `pages/Login.jsx`: "Login" heading, centered card (no form yet — Phase 2)
       - `pages/Register.jsx`: "Register" heading, centered card (no form yet — Phase 2)
       - `pages/NotFound.jsx`: 404 page with "Page Not Found" and link back to home

    6. Update `frontend/src/App.jsx` (minimal changes):
       - Remove Vite boilerplate JSX (counter, logos)
       - Remove import of App.css
       - Import Routes, Route, Outlet from react-router-dom
       - Define routes:
         / → MainLayout → Home
         /login → MainLayout → Login
         /register → MainLayout → Register
         * → MainLayout → NotFound

    7. Update `frontend/src/main.jsx` (minimal change):
       - Add BrowserRouter wrapper around <App />
       - Keep StrictMode

    8. After App.jsx no longer imports App.css, delete App.css (the ONLY file deleted).
       Keep all assets/ files — they may be useful later.

    AVOID: Deleting frontend/src/assets/ — keep existing assets
    AVOID: Complex page content — these are SHELLS, not functional pages
    AVOID: Any auth logic, forms, or API calls — those are Phase 2
    USE: Tailwind utility classes exclusively (no custom CSS files)
    USE: React Router v6+ layout routes pattern (Outlet in MainLayout)
  </action>
  <verify>
    cd frontend
    npm run build
  </verify>
  <done>
    - Build succeeds with zero errors
    - 4 routes defined (/, /login, /register, /*)
    - Navbar renders with navigation links
    - Layout wraps all pages with Navbar + content + Footer
    - Only App.css was deleted; all other existing files preserved
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] Tailwind CSS v4 classes compile in build output
- [ ] React Router navigates between pages
- [ ] Layout shell renders Navbar + content + Footer on every page
- [ ] `npm run build` produces no errors
- [ ] Existing frontend/src/assets/ preserved
- [ ] vite.config.js was extended, not replaced

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] Frontend ready for feature development in Phase 2+

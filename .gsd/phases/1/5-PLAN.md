---
phase: 1
plan: 5
wave: 2
depends_on: [2, 4]
gap_closure: false
---

# Plan 1.5: Seed Data — Synthetic Hospitals & Doctors

## Objective
Create a seed data script that populates the database with realistic but synthetic hospital and doctor data for development and testing. All data is clearly labeled as synthetic.

## Context
Load these files for context:
- .gsd/SPEC.md (Constraints: synthetic data only)
- backend/app/models/hospital.py
- backend/app/models/doctor.py
- backend/app/models/user.py

## Tasks

<task type="auto" effort="medium">
  <name>Create seed data script with synthetic hospitals and doctors</name>
  <files>
    backend/app/scripts/__init__.py
    backend/app/scripts/seed_data.py
  </files>
  <action>
    Create `backend/app/scripts/seed_data.py` that:

    1. Defines synthetic hospital data (10 hospitals) with REAL city coordinates:
       Use actual lat/lng for major Indian cities (Mumbai, Delhi, Bangalore, Chennai, Hyderabad, etc.)
       Each hospital gets:
       - Realistic but clearly synthetic name (e.g., "MediSmart General Hospital - Mumbai [SYNTHETIC]")
       - Real street address format for that city
       - 3-5 specialties from: Cardiology, Orthopedics, Neurology, Pediatrics, Oncology, Dermatology, ENT, Ophthalmology, General Medicine, Emergency
       - 3-5 facilities from: ICU, Emergency, Pharmacy, Lab, Radiology, Blood Bank, Ambulance, Cafeteria, Parking, Wi-Fi

    2. Defines synthetic doctor data (30 doctors, ~3 per hospital):
       Each doctor gets:
       - Realistic Indian name
       - Specialty matching one of their hospital's specialties
       - Qualification (MBBS, MD, MS, etc.)
       - 2-25 years experience (randomized)
       - Consultation fee between 300-2000 INR
       - A corresponding user account with role="doctor"

    3. Creates 5 synthetic patient user accounts for testing:
       - patient1@test.com through patient5@test.com
       - Password: "Test@1234" (hashed with bcrypt)
       - Role: "patient"

    4. Creates 1 system admin account:
       - admin@medismart.com / "Admin@1234"
       - Role: "system_admin"

    5. Script is idempotent — checks if data already exists before inserting.

    6. Can be run via: python -m app.scripts.seed_data

    AVOID: Using random.random() for coordinates — use REAL city coordinates
    AVOID: Generating data without the [SYNTHETIC] label
    USE: passlib bcrypt for password hashing (same as auth will use)
    USE: asyncio.run() as the entry point
  </action>
  <verify>
    cd backend
    python -m app.scripts.seed_data
    docker compose exec db psql -U postgres -d medismart -c "SELECT count(*) FROM hospitals;"
    docker compose exec db psql -U postgres -d medismart -c "SELECT count(*) FROM users;"
  </verify>
  <done>
    - 10 hospitals inserted into database
    - 30 doctor users + 5 patient users + 1 admin user = 36 users total
    - All hospital coordinates are real city locations
    - Script is idempotent (running twice doesn't duplicate data)
    - All synthetic data is labeled
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] 10 hospitals with real geographic coordinates
- [ ] 30 doctors with matching specialties
- [ ] Test accounts with hashed passwords
- [ ] All data clearly labeled as [SYNTHETIC]
- [ ] Script is idempotent

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] Database populated and ready for feature development

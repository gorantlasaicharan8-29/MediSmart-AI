import asyncio
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.hospital import Hospital
from app.models.doctor import Doctor

INITIAL_DOCTORS = [
    {
        "hospital_name": "All India Institute of Medical Sciences (AIIMS)",
        "full_name": "Dr. Rajesh Sharma",
        "email": "dr.rajesh.sharma@medismart.demo",
        "phone": "+91 98110 12345",
        "specialty": "Cardiology",
        "qualification": "MBBS, MD (Medicine), DM (Cardiology), FACC",
        "experience_years": 18,
        "consultation_fee": 1200.0,
        "is_available": True,
        "credential_status": "sample",
        "bio": "Senior Interventional Cardiologist specializing in complex coronary angioplasty, heart failure management, and structural heart interventions. Demonstration profile for AIIMS New Delhi.",
        "available_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    },
    {
        "hospital_name": "All India Institute of Medical Sciences (AIIMS)",
        "full_name": "Dr. Sunita Deshmukh",
        "email": "dr.sunita.deshmukh@medismart.demo",
        "phone": "+91 98110 54321",
        "specialty": "Neurology",
        "qualification": "MBBS, MD (General Medicine), DM (Neurology)",
        "experience_years": 14,
        "consultation_fee": 1100.0,
        "is_available": True,
        "credential_status": "sample",
        "bio": "Consultant Neurologist with clinical focus on acute ischemic stroke management, epilepsy syndromes, and neurodegenerative disorders. Demonstration profile.",
        "available_days": ["Monday", "Wednesday", "Friday"],
    },
    {
        "hospital_name": "Apollo Hospital, Jubilee Hills",
        "full_name": "Dr. Vikram Reddy",
        "email": "dr.vikram.reddy@medismart.demo",
        "phone": "+91 98490 11223",
        "specialty": "Orthopedics",
        "qualification": "MBBS, MS (Orthopedics), MCh (Orth), Fellow Joint Replacement",
        "experience_years": 16,
        "consultation_fee": 1000.0,
        "is_available": True,
        "credential_status": "sample",
        "bio": "Senior Orthopedic Surgeon specializing in robotic total knee and hip arthroplasty and sports medicine. Demonstration profile for Apollo Jubilee Hills.",
        "available_days": ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    },
    {
        "hospital_name": "Apollo Hospital, Jubilee Hills",
        "full_name": "Dr. Ananya Rao",
        "email": "dr.ananya.rao@medismart.demo",
        "phone": "+91 98490 44556",
        "specialty": "Gastroenterology",
        "qualification": "MBBS, MD, DNB (Gastroenterology)",
        "experience_years": 11,
        "consultation_fee": 950.0,
        "is_available": True,
        "credential_status": "sample",
        "bio": "Therapeutic Endoscopist and Hepatologist managing gastrointestinal motility disorders and inflammatory bowel disease. Demonstration profile.",
        "available_days": ["Monday", "Tuesday", "Thursday", "Friday"],
    },
    {
        "hospital_name": "Fortis Memorial Research Institute",
        "full_name": "Dr. Amitava Roy",
        "email": "dr.amitava.roy@medismart.demo",
        "phone": "+91 98101 77889",
        "specialty": "Oncology",
        "qualification": "MBBS, MD (Radiotherapy), DNB (Medical Oncology)",
        "experience_years": 20,
        "consultation_fee": 1500.0,
        "is_available": True,
        "credential_status": "sample",
        "bio": "Director of Medical Oncology with extensive clinical trials experience in targeted immunotherapy and breast oncology. Demonstration profile for Fortis Gurugram.",
        "available_days": ["Monday", "Tuesday", "Wednesday", "Thursday"],
    },
    {
        "hospital_name": "Fortis Memorial Research Institute",
        "full_name": "Dr. Neha Kapoor",
        "email": "dr.neha.kapoor@medismart.demo",
        "phone": "+91 98101 99001",
        "specialty": "Pediatrics",
        "qualification": "MBBS, DCH, DNB (Pediatrics), Fellow Neonatology",
        "experience_years": 9,
        "consultation_fee": 800.0,
        "is_available": True,
        "credential_status": "pending_verification",
        "bio": "Pediatrician and Neonatologist providing comprehensive newborn care, developmental assessments, and immunization. Profile undergoing credential verification.",
        "available_days": ["Monday", "Tuesday", "Wednesday", "Friday", "Saturday"],
    },
    {
        "hospital_name": "Tata Memorial Hospital",
        "full_name": "Dr. Pradeep Kulkarni",
        "email": "dr.pradeep.kulkarni@medismart.demo",
        "phone": "+91 98200 33445",
        "specialty": "Oncology",
        "qualification": "MBBS, MS (Surgical Oncology), FACS",
        "experience_years": 22,
        "consultation_fee": 1200.0,
        "is_available": True,
        "credential_status": "sample",
        "bio": "Chief of Surgical Oncology specializing in minimally invasive gastrointestinal and thoracic cancer resections. Demonstration profile for Tata Memorial Mumbai.",
        "available_days": ["Monday", "Wednesday", "Thursday", "Friday"],
    },
    {
        "hospital_name": "Manipal Hospital, Old Airport Road",
        "full_name": "Dr. Karthik Iyer",
        "email": "dr.karthik.iyer@medismart.demo",
        "phone": "+91 98450 66778",
        "specialty": "Nephrology",
        "qualification": "MBBS, MD (Medicine), DM (Nephrology)",
        "experience_years": 13,
        "consultation_fee": 1000.0,
        "is_available": True,
        "credential_status": "sample",
        "bio": "Senior Consultant Nephrologist and Renal Transplant Physician with expertise in hemodialysis and chronic kidney disease management. Demonstration profile for Manipal Bangalore.",
        "available_days": ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    },
    {
        "hospital_name": "Christian Medical College (CMC)",
        "full_name": "Dr. Mary Thomas",
        "email": "dr.mary.thomas@medismart.demo",
        "phone": "+91 94430 88990",
        "specialty": "Pulmonology",
        "qualification": "MBBS, MD (Pulmonary Medicine), FCCP",
        "experience_years": 15,
        "consultation_fee": 750.0,
        "is_available": True,
        "credential_status": "sample",
        "bio": "Professor of Pulmonology specializing in interstitial lung disease, asthma management, and advanced bronchoscopy. Demonstration profile for CMC Vellore.",
        "available_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    },
    {
        "hospital_name": "Sir Ganga Ram Hospital",
        "full_name": "Dr. Subhashish Mohanty",
        "email": "dr.subhashish.mohanty@medismart.demo",
        "phone": "+91 94370 12345",
        "specialty": "Dermatology",
        "qualification": "MBBS, MD (Dermatology, Venereology & Leprosy)",
        "experience_years": 10,
        "consultation_fee": 700.0,
        "is_available": True,
        "credential_status": "pending_verification",
        "bio": "Consultant Dermatologist focusing on clinical dermatology, psoriasis therapy, and aesthetic dermato-surgery. Profile undergoing hospital credential verification at Sir Ganga Ram Hospital.",
        "available_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Saturday"],
    },
]

DEFAULT_PASSWORD = "DoctorSecurePass123!"


async def seed_doctors():
    """Seeds doctors linked to seeded hospitals idempotently."""
    print("=" * 60)
    print("MediSmart — Seeding Doctor Profiles (Idempotent)")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        # Load all hospitals by name
        hosp_stmt = select(Hospital)
        hosp_result = await session.execute(hosp_stmt)
        hospitals_by_name = {h.name: h for h in hosp_result.scalars().all()}

        if not hospitals_by_name:
            print("ERROR: No hospitals found in database. Please run seed_hospitals.py first.")
            return

        created_count = 0
        skipped_count = 0

        for doc_data in INITIAL_DOCTORS:
            hosp = hospitals_by_name.get(doc_data["hospital_name"])
            if not hosp:
                print(f"[SKIP] Hospital not found: '{doc_data['hospital_name']}'")
                continue

            # Check if User already exists
            user_stmt = select(User).where(User.email == doc_data["email"])
            user_res = await session.execute(user_stmt)
            existing_user = user_res.scalar_one_or_none()

            if existing_user:
                # Check if Doctor profile already exists
                doc_stmt = select(Doctor).where(Doctor.user_id == existing_user.id)
                doc_res = await session.execute(doc_stmt)
                existing_doc = doc_res.scalar_one_or_none()
                if existing_doc:
                    print(f"[EXISTS] Doctor profile for {doc_data['full_name']} ({doc_data['email']}) already exists. Skipping.")
                    skipped_count += 1
                    continue
                user = existing_user
            else:
                # Create user
                user = User(
                    email=doc_data["email"],
                    hashed_password=get_password_hash(DEFAULT_PASSWORD),
                    full_name=doc_data["full_name"],
                    phone=doc_data["phone"],
                    role="doctor",
                    is_active=True,
                )
                session.add(user)
                await session.flush()  # to obtain user.id

            # Create doctor profile
            doctor = Doctor(
                user_id=user.id,
                hospital_id=hosp.id,
                specialty=doc_data["specialty"],
                qualification=doc_data["qualification"],
                experience_years=doc_data["experience_years"],
                consultation_fee=doc_data["consultation_fee"],
                is_available=doc_data["is_available"],
                credential_status=doc_data["credential_status"],
                bio=doc_data["bio"],
                available_days=doc_data["available_days"],
            )
            session.add(doctor)
            created_count += 1
            print(f"[CREATED] {doc_data['full_name']} — {doc_data['specialty']} @ {hosp.name} [{doc_data['credential_status']}]")

        await session.commit()
        print("-" * 60)
        print(f"Doctor seeding complete! Created: {created_count}, Skipped (already existed): {skipped_count}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_doctors())

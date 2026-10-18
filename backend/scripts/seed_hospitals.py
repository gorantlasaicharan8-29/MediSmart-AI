import asyncio
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.hospital import Hospital

INITIAL_HOSPITALS = [
    {
        "name": "All India Institute of Medical Sciences (AIIMS)",
        "address": "Sri Aurobindo Marg, Ansari Nagar",
        "city": "New Delhi",
        "state": "Delhi",
        "latitude": 28.5672,
        "longitude": 77.2100,
        "phone": "+91 11 2658 8500",
        "email": "info@aiims.edu",
        "specialties": ["Cardiology", "Neurology", "Oncology", "Orthopedics", "Pediatrics", "Emergency Medicine"],
        "facilities": ["ICU", "Emergency 24/7", "Blood Bank", "MRI/CT Scan", "Level-1 Trauma Center", "Pharmacy"],
        "is_active": True,
        "data_source": "verified",
        "source_attribution": "© OpenStreetMap contributors",
    },
    {
        "name": "Apollo Hospital, Jubilee Hills",
        "address": "Road No. 72, Opposite Bharatiya Vidya Bhavan, Film Nagar",
        "city": "Hyderabad",
        "state": "Telangana",
        "latitude": 17.4156,
        "longitude": 78.4124,
        "phone": "+91 40 2360 7777",
        "email": "enquiry@apollohyd.com",
        "specialties": ["Cardiology", "Nephrology", "Oncology", "Gastroenterology", "Organ Transplant"],
        "facilities": ["Emergency 24/7", "Trauma Center", "Robotic Surgery", "Dialysis Unit", "Advanced Cath Lab"],
        "is_active": True,
        "data_source": "verified",
        "source_attribution": "© OpenStreetMap contributors",
    },
    {
        "name": "Fortis Memorial Research Institute",
        "address": "Sector 44, Opposite HUDA City Centre Metro Station",
        "city": "Gurugram",
        "state": "Haryana",
        "latitude": 28.4595,
        "longitude": 77.0726,
        "phone": "+91 124 496 2200",
        "email": "contactus@fortishealthcare.com",
        "specialties": ["Neurology", "Oncology", "Orthopedics", "Pulmonology", "Cardiac Surgery"],
        "facilities": ["ICU", "Emergency 24/7", "Advanced Imaging", "Rehabilitation Center", "Blood Bank"],
        "is_active": True,
        "data_source": "verified",
        "source_attribution": "© OpenStreetMap contributors",
    },
    {
        "name": "Manipal Hospital, Old Airport Road",
        "address": "98, HAL Old Airport Rd, Kodihalli",
        "city": "Bengaluru",
        "state": "Karnataka",
        "latitude": 12.9584,
        "longitude": 77.6489,
        "phone": "+91 80 2502 4444",
        "email": "info@manipalhospitals.com",
        "specialties": ["Cardiology", "Pediatrics", "Nephrology", "Organ Transplant", "General Surgery"],
        "facilities": ["Emergency 24/7", "Blood Bank", "NICU/PICU", "PET-CT", "In-house Pharmacy"],
        "is_active": True,
        "data_source": "verified",
        "source_attribution": "© OpenStreetMap contributors",
    },
    {
        "name": "Tata Memorial Hospital",
        "address": "Dr. Ernest Borges Rd, Parel",
        "city": "Mumbai",
        "state": "Maharashtra",
        "latitude": 19.0048,
        "longitude": 72.8428,
        "phone": "+91 22 2417 7000",
        "email": "tmh@tmc.gov.in",
        "specialties": ["Oncology", "Surgical Oncology", "Radiation Oncology", "Hematology"],
        "facilities": ["Cancer Research Center", "Bone Marrow Transplant", "ICU", "Specialized Chemotherapy"],
        "is_active": True,
        "data_source": "verified",
        "source_attribution": "© OpenStreetMap contributors",
    },
    {
        "name": "Sir Ganga Ram Hospital",
        "address": "Rajinder Nagar",
        "city": "New Delhi",
        "state": "Delhi",
        "latitude": 28.6385,
        "longitude": 77.1897,
        "phone": "+91 11 2575 0000",
        "email": "gangaram@sgrh.com",
        "specialties": ["Internal Medicine", "Nephrology", "Gastroenterology", "Cardiology"],
        "facilities": ["ICU", "Dialysis", "Emergency 24/7", "Diagnostic Pathology", "Blood Bank"],
        "is_active": True,
        "data_source": "verified",
        "source_attribution": "© OpenStreetMap contributors",
    },
    {
        "name": "Christian Medical College (CMC)",
        "address": "Ida Scudder Road",
        "city": "Vellore",
        "state": "Tamil Nadu",
        "latitude": 12.9246,
        "longitude": 79.1352,
        "phone": "+91 416 228 1000",
        "email": "directorate@cmcvellore.ac.in",
        "specialties": ["Hematology", "Endocrinology", "Neurology", "Rheumatology", "Dermatology"],
        "facilities": ["Emergency 24/7", "Clinical Laboratories", "Telemedicine Unit", "Blood Bank"],
        "is_active": True,
        "data_source": "verified",
        "source_attribution": "© OpenStreetMap contributors",
    },
    # Sample facility with missing coordinates to test requirement 7 & 8
    {
        "name": "Community Wellness Health Center",
        "address": "Sector 4, Model Town Extension",
        "city": "Jaipur",
        "state": "Rajasthan",
        "latitude": None,
        "longitude": None,
        "phone": "+91 141 278 0000",
        "email": "clinic@wellnesscenter.sample",
        "specialties": ["General Medicine", "Family Practice", "Pediatrics"],
        "facilities": ["Outpatient Clinic", "Basic Lab", "Daycare Observation"],
        "is_active": True,
        "data_source": "sample",
        "source_attribution": "Sample demonstration record (GPS coordinates pending survey)",
    },
]


async def seed_hospitals():
    """Seeds verified and sample hospitals into medismart_db idempotently."""
    async with AsyncSessionLocal() as session:
        added_count = 0
        existing_count = 0

        for h_data in INITIAL_HOSPITALS:
            stmt = select(Hospital).where(
                Hospital.name == h_data["name"],
                Hospital.city == h_data["city"],
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing_count += 1
            else:
                new_hospital = Hospital(**h_data)
                session.add(new_hospital)
                added_count += 1

        await session.commit()
        print(f"Hospital Seeding Completed: {added_count} added, {existing_count} already existed.")


if __name__ == "__main__":
    asyncio.run(seed_hospitals())

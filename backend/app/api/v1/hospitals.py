import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.hospital import Hospital
from app.schemas.hospital import (
    HospitalCreate,
    HospitalListResponse,
    HospitalResponse,
    HospitalUpdate,
)

router = APIRouter()


@router.get(
    "",
    response_model=HospitalListResponse,
    summary="Search and discover hospital facilities with geo and facet filtering",
)
async def list_hospitals(
    search: Optional[str] = Query(None, description="Search by name, address, or city"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    specialty: Optional[str] = Query(None, description="Filter by clinical specialty"),
    facility: Optional[str] = Query(None, description="Filter by facility capability"),
    data_source: Optional[str] = Query(None, description="Filter by data source: verified, sample"),
    has_coords: Optional[bool] = Query(None, description="Filter by presence of geographic coordinates"),
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Latitude for proximity search"),
    lng: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Longitude for proximity search"),
    radius_km: Optional[float] = Query(None, gt=0, description="Search radius in kilometers"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Public discovery endpoint. Supports text search, city filtering, PostgreSQL array filtering
    for specialties and facilities, and spatial distance bounding using the Haversine formula.
    """
    stmt = select(Hospital).where(Hospital.is_active == True)

    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Hospital.name.ilike(term),
                Hospital.address.ilike(term),
                Hospital.city.ilike(term),
                Hospital.state.ilike(term),
            )
        )

    if city and city.strip():
        stmt = stmt.where(Hospital.city.ilike(city.strip()))

    if specialty and specialty.strip():
        stmt = stmt.where(Hospital.specialties.contains([specialty.strip()]))

    if facility and facility.strip():
        stmt = stmt.where(Hospital.facilities.contains([facility.strip()]))

    if data_source and data_source.strip():
        stmt = stmt.where(Hospital.data_source == data_source.strip().lower())

    if has_coords is True:
        stmt = stmt.where(Hospital.latitude.isnot(None), Hospital.longitude.isnot(None))
    elif has_coords is False:
        stmt = stmt.where(or_(Hospital.latitude.is_(None), Hospital.longitude.is_(None)))

    # Spatial proximity search if coordinates and radius provided
    if lat is not None and lng is not None and radius_km is not None:
        stmt = stmt.where(Hospital.latitude.isnot(None), Hospital.longitude.isnot(None))
        rad_lat = math.radians(lat)
        rad_lng = math.radians(lng)

        distance_expr = (
            6371.0
            * func.acos(
                func.least(
                    1.0,
                    func.greatest(
                        -1.0,
                        func.cos(rad_lat)
                        * func.cos(func.radians(Hospital.latitude))
                        * func.cos(func.radians(Hospital.longitude) - rad_lng)
                        + func.sin(rad_lat) * func.sin(func.radians(Hospital.latitude)),
                    ),
                )
            )
        )
        stmt = stmt.where(distance_expr <= radius_km).order_by(distance_expr)
    else:
        stmt = stmt.order_by(Hospital.name.asc())

    # Calculate total count for pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch paginated items
    paginated_stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(paginated_stmt)
    hospitals = result.scalars().all()

    return HospitalListResponse(
        items=[HospitalResponse.model_validate(h) for h in hospitals],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{hospital_id}",
    response_model=HospitalResponse,
    summary="Get single hospital details by ID",
)
async def get_hospital(
    hospital_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Public detail endpoint for a single hospital facility."""
    stmt = select(Hospital).where(Hospital.id == hospital_id)
    result = await db.execute(stmt)
    hospital = result.scalar_one_or_none()

    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    return hospital


@router.post(
    "",
    response_model=HospitalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new hospital facility (Hospital Admin / System Admin only)",
    dependencies=[Depends(require_roles("hospital_admin", "system_admin"))],
)
async def create_hospital(
    payload: HospitalCreate,
    db: AsyncSession = Depends(get_db),
):
    """Restricted to hospital_admin and system_admin roles."""
    new_hospital = Hospital(**payload.model_dump())
    db.add(new_hospital)
    await db.commit()
    await db.refresh(new_hospital)
    return new_hospital


@router.put(
    "/{hospital_id}",
    response_model=HospitalResponse,
    summary="Update hospital facility details (Hospital Admin / System Admin only)",
    dependencies=[Depends(require_roles("hospital_admin", "system_admin"))],
)
async def update_hospital(
    hospital_id: uuid.UUID,
    payload: HospitalUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Restricted to hospital_admin and system_admin roles."""
    stmt = select(Hospital).where(Hospital.id == hospital_id)
    result = await db.execute(stmt)
    hospital = result.scalar_one_or_none()

    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(hospital, field, value)

    await db.commit()
    await db.refresh(hospital)
    return hospital


@router.delete(
    "/{hospital_id}",
    summary="Delete a hospital facility (System Admin only)",
    dependencies=[Depends(require_roles("system_admin"))],
)
async def delete_hospital(
    hospital_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Restricted exclusively to system_admin role."""
    stmt = select(Hospital).where(Hospital.id == hospital_id)
    result = await db.execute(stmt)
    hospital = result.scalar_one_or_none()

    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    await db.delete(hospital)
    await db.commit()
    return {"message": "Hospital removed successfully", "id": str(hospital_id)}

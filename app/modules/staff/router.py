from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.audit import write_audit_log
from app.core.crud import get_owned_or_404
from app.core.deps import DbDep, Owner
from app.core.security import hash_password
from app.models import Invoice, User, UserRole
from app.modules.staff.schemas import StaffCreate, StaffResponse, StaffUpdate

router = APIRouter(prefix="/staff", tags=["staff"])


def _to_staff_response(db: DbDep, staff: User) -> StaffResponse:
    assigned_count = (
        db.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.assigned_to_id == staff.id)
        )
        or 0
    )
    return StaffResponse(
        id=staff.id,
        email=staff.email,
        full_name=staff.full_name,
        role=staff.role,
        is_active=staff.is_active,
        created_at=staff.created_at,
        assigned_invoice_count=assigned_count,
    )


def _get_staff_or_404(db: DbDep, staff_id: UUID, organization_id: UUID) -> User:
    staff = get_owned_or_404(
        db,
        User,
        record_id=staff_id,
        organization_id=organization_id,
        detail="Staff member not found",
    )
    if staff.role is not UserRole.STAFF:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )
    return staff


@router.post("", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
def create_staff(payload: StaffCreate, owner: Owner, db: DbDep) -> StaffResponse:
    """Create a STAFF account within the owner's organization."""
    if db.scalar(select(User).where(User.email == payload.email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    staff = User(
        organization_id=owner.organization_id,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.STAFF,
    )
    db.add(staff)
    db.flush()
    db.refresh(staff)

    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="staff.created",
        resource_type="user",
        resource_id=staff.id,
    )
    db.commit()

    return _to_staff_response(db, staff)


@router.get("", response_model=list[StaffResponse])
def list_staff(owner: Owner, db: DbDep) -> list[StaffResponse]:
    """List all staff in the owner's organization."""
    staff_members = db.scalars(
        select(User)
        .where(
            User.organization_id == owner.organization_id,
            User.role == UserRole.STAFF,
        )
        .order_by(User.created_at)
    ).all()
    return [_to_staff_response(db, staff) for staff in staff_members]


@router.get("/{staff_id}", response_model=StaffResponse)
def get_staff(staff_id: UUID, owner: Owner, db: DbDep) -> StaffResponse:
    """Return a single staff member."""
    staff = _get_staff_or_404(db, staff_id, owner.organization_id)
    return _to_staff_response(db, staff)


@router.patch("/{staff_id}", response_model=StaffResponse)
def update_staff(
    staff_id: UUID,
    payload: StaffUpdate,
    owner: Owner,
    db: DbDep,
) -> StaffResponse:
    """Update a staff member's name, status, or password."""
    staff = _get_staff_or_404(db, staff_id, owner.organization_id)
    updates = payload.model_dump(exclude_unset=True)

    if "password" in updates:
        new_password = updates.pop("password")
        if new_password is not None:
            updates["password_hash"] = hash_password(new_password)

    for field, value in updates.items():
        if value is not None:
            setattr(staff, field, value)

    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="staff.updated",
        resource_type="user",
        resource_id=staff.id,
    )
    db.commit()
    db.refresh(staff)
    return _to_staff_response(db, staff)


@router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_staff(staff_id: UUID, owner: Owner, db: DbDep) -> None:
    """Deactivate a staff member (revokes their access)."""
    staff = _get_staff_or_404(db, staff_id, owner.organization_id)
    staff.is_active = False
    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="staff.deactivated",
        resource_type="user",
        resource_id=staff.id,
    )
    db.commit()

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.audit import write_audit_log
from app.core.deps import CurrentUser, DbDep, Owner
from app.models import Client, Invoice, Organization, User, UserRole
from app.modules.organizations.schemas import OrganizationResponse, OrganizationUpdate

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _to_org_response(db: DbDep, org: Organization) -> OrganizationResponse:
    staff_count = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.organization_id == org.id, User.role == UserRole.STAFF)
        )
        or 0
    )
    client_count = (
        db.scalar(
            select(func.count()).select_from(Client).where(Client.organization_id == org.id)
        )
        or 0
    )
    invoice_count = (
        db.scalar(
            select(func.count()).select_from(Invoice).where(Invoice.organization_id == org.id)
        )
        or 0
    )
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        is_active=org.is_active,
        created_at=org.created_at,
        staff_count=staff_count,
        client_count=client_count,
        invoice_count=invoice_count,
    )


@router.get("/me", response_model=OrganizationResponse)
def get_my_organization(
    current_user: CurrentUser,
    db: DbDep,
) -> OrganizationResponse:
    """Return the authenticated user's organization and usage counts."""
    return _to_org_response(db, current_user.organization)


@router.patch("/me", response_model=OrganizationResponse)
def update_my_organization(
    payload: OrganizationUpdate,
    owner: Owner,
    db: DbDep,
) -> OrganizationResponse:
    """Update the owner's organization name."""
    org = owner.organization
    org.name = payload.name
    write_audit_log(
        db,
        organization_id=org.id,
        actor_id=owner.id,
        action="organization.updated",
        resource_type="organization",
        resource_id=org.id,
    )
    db.commit()
    db.refresh(org)
    return _to_org_response(db, org)

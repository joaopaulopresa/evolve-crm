from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_session
from app.models import Company, Contact
from app.schemas import ContactIn, ContactOut, ContactPatch

router = APIRouter(prefix="/api/contacts", tags=["contacts"], dependencies=[Depends(current_user)])


def to_out(contact: Contact) -> ContactOut:
    return ContactOut.model_validate(
        {
            **{column.name: getattr(contact, column.name) for column in Contact.__table__.columns},
            "company_name": contact.company.name if contact.company else None,
        }
    )


def get_contact(contact_id: int, session: Session = Depends(get_session)) -> Contact:
    contact = session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return contact


@router.get("", response_model=list[ContactOut])
def list_contacts(
    q: str | None = None, company_id: int | None = None, session: Session = Depends(get_session)
):
    query = (
        select(Contact)
        .outerjoin(Company, Contact.company_id == Company.id)
        .order_by(Contact.first_name, Contact.last_name)
    )
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                (Contact.first_name + " " + Contact.last_name).ilike(pattern),
                Contact.email.ilike(pattern),
                Company.name.ilike(pattern),
            )
        )
    if company_id:
        query = query.where(Contact.company_id == company_id)
    return [to_out(contact) for contact in session.scalars(query).all()]


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactIn, session: Session = Depends(get_session)):
    contact = Contact(**payload.model_dump())
    session.add(contact)
    session.commit()
    return to_out(contact)


@router.get("/{contact_id}", response_model=ContactOut)
def read_contact(contact: Contact = Depends(get_contact)):
    return to_out(contact)


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    payload: ContactPatch,
    contact: Contact = Depends(get_contact),
    session: Session = Depends(get_session),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    session.commit()
    session.refresh(contact)
    return to_out(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact: Contact = Depends(get_contact), session: Session = Depends(get_session)
):
    session.delete(contact)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

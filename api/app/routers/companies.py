from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_session
from app.models import Company
from app.schemas import CompanyIn, CompanyOut, CompanyPatch

router = APIRouter(
    prefix="/api/companies", tags=["companies"], dependencies=[Depends(current_user)]
)


def get_company(company_id: int, session: Session = Depends(get_session)) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return company


@router.get("", response_model=list[CompanyOut])
def list_companies(
    q: str | None = None, industry: str | None = None, session: Session = Depends(get_session)
):
    query = select(Company).order_by(Company.name)
    if q:
        query = query.where(Company.name.ilike(f"%{q}%"))
    if industry:
        query = query.where(Company.industry == industry)
    return session.scalars(query).all()


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyIn, session: Session = Depends(get_session)):
    company = Company(**payload.model_dump())
    session.add(company)
    session.commit()
    return company


@router.get("/{company_id}", response_model=CompanyOut)
def read_company(company: Company = Depends(get_company)):
    return company


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    payload: CompanyPatch,
    company: Company = Depends(get_company),
    session: Session = Depends(get_session),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    session.commit()
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company: Company = Depends(get_company), session: Session = Depends(get_session)
):
    session.delete(company)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

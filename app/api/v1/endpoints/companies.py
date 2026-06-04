from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import require_admin, require_super_admin
from app.services.company import CompanyService
from app.schemas.company import (
    CompanyRead, CompanyCreate, CompanyUpdate,
    PaginatedCompanies, PaginatedClients,
)
from app.schemas.user import PaginatedUsers

router = APIRouter()

@router.get("/", response_model=PaginatedCompanies, dependencies=[Depends(require_super_admin)])
def list_companies(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    is_blocked: bool | None = Query(None),
):
    return CompanyService.get_all(db, page, page_size, search, status, is_blocked)

@router.post("/", response_model=CompanyRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_super_admin)])
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    return CompanyService.create(db, payload)

@router.get("/{company_id}", response_model=CompanyRead, dependencies=[Depends(require_admin)])
def get_company(company_id: int, db: Session = Depends(get_db)):
    return CompanyService.get_by_id(db, company_id)

@router.put("/{company_id}", response_model=CompanyRead, dependencies=[Depends(require_admin)])
def update_company(company_id: int, payload: CompanyUpdate, db: Session = Depends(get_db)):
    return CompanyService.update(db, company_id, payload)

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_super_admin)])
def delete_company(company_id: int, db: Session = Depends(get_db)):
    CompanyService.delete(db, company_id)

@router.patch("/{company_id}/block", response_model=CompanyRead,
              dependencies=[Depends(require_super_admin)])
def toggle_block(company_id: int, db: Session = Depends(get_db)):
    return CompanyService.toggle_block(db, company_id)

@router.get("/{company_id}/users", response_model=PaginatedUsers,
            dependencies=[Depends(require_admin)])
def get_company_users(
    company_id: int,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return CompanyService.get_users(db, company_id, page, page_size)

@router.get("/{company_id}/clients", response_model=PaginatedClients,
            dependencies=[Depends(require_admin)])
def get_company_clients(
    company_id: int,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    is_blocked: bool | None = Query(None),
):
    return CompanyService.get_clients(db, company_id, page, page_size, status, is_blocked)
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import require_admin, require_super_admin
from app.services.company import ClientService
from app.schemas.company import (
    ClientRead, ClientCreate, ClientUpdate,
    PaginatedClients,
)
from app.schemas.user import PaginatedUsers

router = APIRouter()

@router.get("/", response_model=PaginatedClients, dependencies=[Depends(require_admin)])
def list_clients(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_id: int | None = Query(None),
    system_type: str | None = Query(None),
    status: str | None = Query(None),
    is_blocked: bool | None = Query(None),
    search: str | None = Query(None),
):
    return ClientService.get_all(
        db, page, page_size, company_id, system_type, status, is_blocked, search
    )

@router.post("/", response_model=ClientRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    return ClientService.create(db, payload)

@router.get("/{client_id}", response_model=ClientRead, dependencies=[Depends(require_admin)])
def get_client(client_id: int, db: Session = Depends(get_db)):
    return ClientService.get_by_id(db, client_id)

@router.put("/{client_id}", response_model=ClientRead, dependencies=[Depends(require_admin)])
def update_client(client_id: int, payload: ClientUpdate, db: Session = Depends(get_db)):
    return ClientService.update(db, client_id, payload)

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_super_admin)])
def delete_client(client_id: int, db: Session = Depends(get_db)):
    ClientService.delete(db, client_id)

@router.patch("/{client_id}/block", response_model=ClientRead,
              dependencies=[Depends(require_admin)])
def toggle_block(client_id: int, db: Session = Depends(get_db)):
    return ClientService.toggle_block(db, client_id)

@router.get("/{client_id}/users", response_model=PaginatedUsers,
            dependencies=[Depends(require_admin)])
def get_client_users(
    client_id: int,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return ClientService.get_users(db, client_id, page, page_size)
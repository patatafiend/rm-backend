from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import Company, Client, UserModel
from app.schemas.company import (
    CompanyCreate, CompanyUpdate,
    ClientCreate, ClientUpdate,
)


class CompanyService:
    
    @staticmethod
    def get_all(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
        is_blocked: bool | None = None,
    ) -> dict:
        query = db.query(Company)

        if search:
            like = f"%{search}%"
            query = query.filter(
                Company.company_name.ilike(like)
                | Company.company_email.ilike(like)
            )
        if status:
            query = query.filter(Company.status == status)
        if is_blocked is not None:
            query = query.filter(Company.is_blocked == is_blocked)

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    @staticmethod
    def get_by_id(db: Session, company_id: int) -> Company:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return company

    @staticmethod
    def create(db: Session, payload: CompanyCreate) -> Company:
        existing = db.query(Company).filter(
            Company.company_email == payload.company_email
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Company email already registered")

        company = Company(**payload.model_dump())
        db.add(company)
        db.commit()
        db.refresh(company)
        return company

    @staticmethod
    def update(db: Session, company_id: int, payload: CompanyUpdate) -> Company:
        company = CompanyService.get_by_id(db, company_id)

        data = payload.model_dump(exclude_none=True)
        if "company_email" in data:
            conflict = db.query(Company).filter(
                Company.company_email == data["company_email"],
                Company.id != company_id,
            ).first()
            if conflict:
                raise HTTPException(status_code=409, detail="Email already in use")

        for field, value in data.items():
            setattr(company, field, value)
        db.commit()
        db.refresh(company)
        return company

    @staticmethod
    def delete(db: Session, company_id: int):
        company = CompanyService.get_by_id(db, company_id)
        db.delete(company)
        db.commit()

    @staticmethod
    def toggle_block(db: Session, company_id: int) -> Company:
        company = CompanyService.get_by_id(db, company_id)
        company.is_blocked = not company.is_blocked
        db.commit()
        db.refresh(company)
        return company

    @staticmethod
    def get_users(
        db: Session,
        company_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        CompanyService.get_by_id(db, company_id)
        query = db.query(UserModel).filter(UserModel.company_id == company_id)
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    @staticmethod
    def get_clients(
        db: Session,
        company_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        is_blocked: bool | None = None,
    ) -> dict:
        CompanyService.get_by_id(db, company_id)
        query = db.query(Client).filter(Client.company_id == company_id)

        if status:
            query = query.filter(Client.status == status)
        if is_blocked is not None:
            query = query.filter(Client.is_blocked == is_blocked)

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size, "items": items}


class ClientService:

    @staticmethod
    def get_all(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        company_id: int | None = None,
        system_type: str | None = None,
        status: str | None = None,
        is_blocked: bool | None = None,
        search: str | None = None,
    ) -> dict:
        query = db.query(Client)

        if company_id:
            query = query.filter(Client.company_id == company_id)
        if system_type:
            query = query.filter(Client.system_type == system_type)
        if status:
            query = query.filter(Client.status == status)
        if is_blocked is not None:
            query = query.filter(Client.is_blocked == is_blocked)
        if search:
            like = f"%{search}%"
            query = query.filter(
                Client.client_name.ilike(like)
                | Client.client_email.ilike(like)
            )

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    @staticmethod
    def get_by_id(db: Session, client_id: int) -> Client:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        return client

    @staticmethod
    def create(db: Session, payload: ClientCreate) -> Client:
        # verify company exists
        company = db.query(Company).filter(Company.id == payload.company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        if company.is_blocked:
            raise HTTPException(status_code=403, detail="Company is blocked")

        existing = db.query(Client).filter(
            Client.client_email == payload.client_email
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Client email already registered")

        client = Client(**payload.model_dump())
        db.add(client)
        db.commit()
        db.refresh(client)
        return client

    @staticmethod
    def update(db: Session, client_id: int, payload: ClientUpdate) -> Client:
        client = ClientService.get_by_id(db, client_id)

        data = payload.model_dump(exclude_none=True)
        if "client_email" in data:
            conflict = db.query(Client).filter(
                Client.client_email == data["client_email"],
                Client.id != client_id,
            ).first()
            if conflict:
                raise HTTPException(status_code=409, detail="Email already in use")

        for field, value in data.items():
            setattr(client, field, value)
        db.commit()
        db.refresh(client)
        return client

    @staticmethod
    def delete(db: Session, client_id: int):
        client = ClientService.get_by_id(db, client_id)
        db.delete(client)
        db.commit()

    @staticmethod
    def toggle_block(db: Session, client_id: int) -> Client:
        client = ClientService.get_by_id(db, client_id)
        client.is_blocked = not client.is_blocked
        db.commit()
        db.refresh(client)
        return client

    @staticmethod
    def get_users(
        db: Session,
        client_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        ClientService.get_by_id(db, client_id)
        query = db.query(UserModel).filter(UserModel.client_id == client_id)
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size, "items": items}
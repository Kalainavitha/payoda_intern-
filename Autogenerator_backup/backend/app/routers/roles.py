from fastapi import APIRouter, status
from app.repositories import sqlite_repo
from app.schemas import RoleCreate

router = APIRouter(prefix="/api/roles", tags=["Roles"])

@router.get("")
def list_roles() -> list[str]:
    return sqlite_repo.list_roles()

@router.post("", status_code=status.HTTP_201_CREATED)
def create_role(request: RoleCreate) -> dict[str, str]:
    name = request.name.strip()
    sqlite_repo.save_role(name)
    return {"name": name}
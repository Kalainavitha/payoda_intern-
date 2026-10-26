from __future__ import annotations

import uuid
from typing import Any
from fastapi import APIRouter, HTTPException, status

from app.repositories import sqlite_repo
from app.schemas import EmployeeCreate, EmployeeUpdate

router = APIRouter(prefix="/api/employees", tags=["Employees"])


@router.get("")
def list_employees() -> list[dict[str, Any]]:
    return sqlite_repo.list_employees()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_employee(request: EmployeeCreate) -> dict[str, Any]:
    employee = request.model_dump(mode="json")
    employee["id"] = str(uuid.uuid4())
    
    # Clean up list fields to remove empty strings and duplicates
    employee["skills"] = list(dict.fromkeys(skill.strip() for skill in employee.get("skills", []) if skill.strip()))
    employee["additional_roles"] = list(dict.fromkeys(role.strip() for role in employee.get("additional_roles", []) if role.strip()))
    
    employee["role"] = employee.get("role", "").strip()
    
    sqlite_repo.save_role(employee["role"])
    sqlite_repo.save_employee(employee)
    return employee


# FIXED: Added @router.put alongside @router.patch so both HTTP methods work
@router.patch("/{employee_id}")
@router.put("/{employee_id}")
def update_employee(employee_id: str, request: EmployeeUpdate) -> dict[str, Any]:
    employee = sqlite_repo.get_employee(employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    
    # Update only the fields that were provided in the request
    update_data = request.model_dump(mode="json", exclude_unset=True)
    employee.update(update_data)
    
    if "role" in employee:
        employee["role"] = employee["role"].strip()
        sqlite_repo.save_role(employee["role"])
        
    sqlite_repo.save_employee(employee)
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: str) -> None:
    if not sqlite_repo.delete_employee(employee_id):
        raise HTTPException(status_code=404, detail="Employee not found.")
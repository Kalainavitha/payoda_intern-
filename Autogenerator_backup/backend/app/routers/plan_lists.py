from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.repositories import sqlite_repo

# Separate from plans.py (which owns /api/projects/{id}/plan) so the two
# prefixes never collide with /api/projects/{project_id}.
router = APIRouter(prefix="/api", tags=["Plan lists"])


@router.get("/plans")
def list_plans() -> list[dict[str, Any]]:
    """Active generated plans."""
    return sqlite_repo.list_plans()


@router.get("/archive")
def list_archive() -> list[dict[str, Any]]:
    """Archived plans."""
    return sqlite_repo.list_archived_plans()


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str) -> dict[str, Any]:
    plan = sqlite_repo.get_plan_by_id(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return plan


@router.post("/plans/{plan_id}/archive")
def archive_plan(plan_id: str) -> dict[str, Any]:
    if not sqlite_repo.archive_plan(plan_id):
        raise HTTPException(status_code=404, detail="Active plan not found.")
    return {"id": plan_id, "status": "archived"}


@router.post("/plans/{plan_id}/restore")
def restore_plan(plan_id: str) -> dict[str, Any]:
    if not sqlite_repo.restore_plan(plan_id):
        raise HTTPException(status_code=404, detail="Archived plan not found.")
    return {"id": plan_id, "status": "active"}


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: str) -> None:
    if not sqlite_repo.delete_plan(plan_id):
        raise HTTPException(status_code=404, detail="Plan not found.")
from __future__ import annotations

import csv
import io
import json
import traceback
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.repositories import sqlite_repo
from app.services import plan_service

router = APIRouter(prefix="/api/projects", tags=["Plans"])

@router.post("/{project_id}/plan")
def create_plan(project_id: str) -> dict[str, Any]:
    try:
        # The service layer handles fetching project, employees, running the scheduler, and saving.
        result = plan_service.create_and_save_plan(project_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Print to the backend terminal for debugging
        traceback.print_exc()
        # Return the actual error message to the frontend
        raise HTTPException(status_code=500, detail=f"Backend Error: {str(e)}")

@router.get("/{project_id}/plan")
def get_plan(project_id: str) -> dict[str, Any]:
    if sqlite_repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    plan = sqlite_repo.get_current_plan(project_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan has been generated for this project yet.")
    return plan

@router.get("/{project_id}/plan/export")
def export_plan(project_id: str, format: str = "json") -> StreamingResponse:
    if sqlite_repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    plan = sqlite_repo.get_current_plan(project_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="No plan has been generated for this project yet.")
        
    if format.casefold() == "json":
        content = json.dumps(plan, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()), 
            media_type="application/json", 
            headers={"Content-Disposition": f'attachment; filename="{project_id}-plan.json"'}
        )
        
    if format.casefold() == "csv":
        output = io.StringIO()
        fields = ["id", "title", "description", "priority", "estimate_hours", "start_date", "end_date", "assigned_employee", "assigned_role", "dependencies"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for task in plan.get("tasks", []):
            row = {**task, "dependencies": ", ".join(task.get("dependencies", []))}
            writer.writerow(row)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")), 
            media_type="text/csv; charset=utf-8", 
            headers={"Content-Disposition": f'attachment; filename="{project_id}-plan.csv"'}
        )
    raise HTTPException(status_code=422, detail="Format must be 'csv' or 'json'.")
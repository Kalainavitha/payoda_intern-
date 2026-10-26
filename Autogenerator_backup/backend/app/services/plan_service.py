from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.repositories import sqlite_repo
from app.services.scheduler import generate_schedule

def create_and_save_plan(project_id: str) -> dict[str, Any]:
    """Orchestrates the plan generation process."""
    project = sqlite_repo.get_project(project_id)
    if not project:
        raise ValueError("Project not found")

    employees = sqlite_repo.list_employees()
    
    # Extract tasks from the project payload
    tasks = project.get("tasks", [])
    if not tasks:
        raise ValueError("No tasks found to schedule")

    # Format the project data for the scheduler
    scheduler_project_data = {
        "start_date": project.get("start_date"),
        "deadline": project.get("end_date"),
        "working_days": project.get("working_days", [0, 1, 2, 3, 4]),
    }
    
    # Run the deterministic scheduler
    schedule_result = generate_schedule(
        project=scheduler_project_data,
        tasks=tasks,
        employees=employees,
        holidays=project.get("public_holidays", [])
    )

    # Prepare the final plan object
    plan = {
        "plan_id": str(uuid.uuid4()),
        "project_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": project.get("start_date"),
        "deadline": project.get("end_date"),
        **schedule_result
    }

    # Save to database
    sqlite_repo.save_plan(project_id, plan)
    
    return plan
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.repositories import sqlite_repo
from app.services.scheduler import generate_schedule


def _holiday_dates(raw: Any) -> list[str]:
    """Holidays may be ISO strings (POST /projects) or {date, name} objects
    (POST /projects/{id}/holidays). The scheduler only understands strings."""
    dates: list[str] = []
    for item in raw or []:
        value = item.get("date") if isinstance(item, dict) else item
        if value:
            dates.append(str(value)[:10])
    return list(dict.fromkeys(dates))


def _with_roles(employee: dict[str, Any]) -> dict[str, Any]:
    """The scheduler reads employee['roles']; employees are stored with
    role / custom_role / additional_roles, so build the combined list here."""
    primary = str(employee.get("role") or "").strip()
    custom = str(employee.get("custom_role") or "").strip()
    candidates = [custom or primary, *(employee.get("additional_roles") or [])]
    if primary and primary.casefold() != "other":
        candidates.insert(0, primary)

    roles: list[str] = []
    seen: set[str] = set()
    for role in candidates:
        role = str(role or "").strip()
        if role and role.casefold() not in seen:
            seen.add(role.casefold())
            roles.append(role)
    return {**employee, "roles": roles}


def create_and_save_plan(project_id: str) -> dict[str, Any]:
    """Orchestrates the plan generation process."""
    project = sqlite_repo.get_project(project_id)
    if not project:
        raise ValueError("Project not found")

    tasks = project.get("tasks", [])
    if not tasks:
        raise ValueError("No tasks found to schedule")

    employees = [_with_roles(e) for e in sqlite_repo.list_employees()]
    if not employees:
        raise ValueError("No team members found. Add at least one team member before generating a plan.")

    # ProjectCreate stores 'deadline' and 'holidays' (older rows may use 'end_date').
    start_date = project.get("start_date")
    deadline = project.get("deadline") or project.get("end_date")
    if not start_date or not deadline:
        raise ValueError(
            f"Project dates are missing (start_date={start_date!r}, deadline={deadline!r})."
        )

    schedule_result = generate_schedule(
        project={
            "start_date": start_date,
            "deadline": deadline,
            "working_days": project.get("working_days") or [0, 1, 2, 3, 4],
        },
        tasks=tasks,
        employees=employees,
        holidays=_holiday_dates(project.get("holidays")),
    )

    plan = {
        "plan_id": str(uuid.uuid4()),
        "project_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": start_date,
        "deadline": deadline,
        **schedule_result,
    }

    sqlite_repo.save_plan(project_id, plan)
    return plan
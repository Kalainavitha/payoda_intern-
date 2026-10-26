from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

# Project structure:
#
# backend/
# ├── app/
# │   └── repositories/
# │       └── sqlite_repo.py
# └── data/
#     └── autoplan.db
#
# parents[2] points to the backend directory.
BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_DATABASE_PATH = BASE_DIR / "data" / "autoplan.db"

DATABASE_PATH = Path(
    os.getenv("DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
).resolve()


# ============================================================
# DATABASE CONNECTION
# ============================================================

def _connect() -> sqlite3.Connection:
    """
    Create a SQLite connection.

    The database directory is created automatically if it
    does not already exist.
    """
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")

    return connection


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """
    Transaction-safe database connection.

    Any exception automatically rolls back the transaction.
    """
    db = _connect()

    try:
        yield db
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database() -> None:
    """
    Create all required database tables.
    """

    with connection() as db:

        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'draft'
            );

            CREATE TABLE IF NOT EXISTS employees (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                years_of_experience INTEGER NOT NULL DEFAULT 0
                    CHECK (years_of_experience >= 0)
            );

            CREATE TABLE IF NOT EXISTS roles (
                name TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS plans (
                project_id TEXT PRIMARY KEY
                    REFERENCES projects(id) ON DELETE CASCADE,
                payload TEXT NOT NULL,
                generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS plan_history (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL
                    REFERENCES projects(id) ON DELETE CASCADE,
                payload TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                archived_at TEXT
            );

            CREATE TABLE IF NOT EXISTS archived_tasks (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                project_name TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                employee_id TEXT,
                employee_name TEXT NOT NULL,
                role TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                status TEXT NOT NULL,
                completed_at TEXT,
                payload TEXT NOT NULL,
                archived_at TEXT NOT NULL
            );
            """
        )


# ============================================================
# PROJECTS
# ============================================================

def save_project(project: dict[str, Any]) -> None:
    """
    Create or update a project.

    IMPORTANT:
    This function does NOT create a new project when the ID
    already exists.

    The same project ID is updated instead.

    A project should normally be saved only after successful
    plan generation.
    """

    project_id = project.get("id")

    if not project_id:
        raise ValueError("Project ID is required")

    requested_status = project.get("status", "draft")

    allowed_statuses = {
        "draft",
        "generating",
        "generated",
        "failed",
        "deleted",
    }

    if requested_status not in allowed_statuses:
        raise ValueError(
            f"Invalid project status: {requested_status}"
        )

    with connection() as db:

        existing = db.execute(
            """
            SELECT status
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

        # If this project already exists, preserve its current
        # status unless a new explicit status is supplied.
        if existing:
            current_status = existing["status"]

            status = requested_status

            # Never accidentally move a generated project back
            # to draft when another save occurs.
            if (
                current_status == "generated"
                and requested_status == "draft"
            ):
                status = "generated"

        else:
            status = requested_status

        project["status"] = status

        db.execute(
            """
            INSERT INTO projects (
                id,
                payload,
                status
            )
            VALUES (?, ?, ?)

            ON CONFLICT(id)
            DO UPDATE SET
                payload = excluded.payload,
                status = excluded.status
            """,
            (
                project_id,
                json.dumps(project),
                status,
            ),
        )


def get_project(
    project_id: str,
) -> dict[str, Any] | None:

    with connection() as db:

        row = db.execute(
            """
            SELECT payload, status
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

    if not row:
        return None

    project = json.loads(row["payload"])

    project["status"] = row["status"]

    return project


def list_projects() -> list[dict[str, Any]]:

    with connection() as db:

        rows = db.execute(
            """
            SELECT payload, status
            FROM projects
            ORDER BY created_at DESC
            """
        ).fetchall()

    projects = []

    for row in rows:

        project = json.loads(row["payload"])

        project["status"] = row["status"]

        projects.append(project)

    return projects


def delete_project(project_id: str) -> bool:

    with connection() as db:

        cursor = db.execute(
            """
            DELETE FROM projects
            WHERE id = ?
            """,
            (project_id,),
        )

    return cursor.rowcount > 0


# ============================================================
# EMPLOYEES
# ============================================================

def save_employee(employee: dict[str, Any]) -> None:

    employee_id = employee.get("id")

    if not employee_id:
        raise ValueError("Employee ID is required")

    years_of_experience = int(
        employee.get("years_of_experience", 0)
    )

    if years_of_experience < 0:
        raise ValueError(
            "Years of experience cannot be negative"
        )

    employee["years_of_experience"] = years_of_experience

    with connection() as db:

        db.execute(
            """
            INSERT INTO employees (
                id,
                payload,
                years_of_experience
            )
            VALUES (?, ?, ?)

            ON CONFLICT(id)
            DO UPDATE SET
                payload = excluded.payload,
                years_of_experience =
                    excluded.years_of_experience
            """,
            (
                employee_id,
                json.dumps(employee),
                years_of_experience,
            ),
        )


def get_employee(
    employee_id: str,
) -> dict[str, Any] | None:

    with connection() as db:

        row = db.execute(
            """
            SELECT payload, years_of_experience
            FROM employees
            WHERE id = ?
            """,
            (employee_id,),
        ).fetchone()

    if not row:
        return None

    employee = json.loads(row["payload"])

    employee["years_of_experience"] = (
        row["years_of_experience"]
    )

    return employee


def list_employees() -> list[dict[str, Any]]:

    with connection() as db:

        rows = db.execute(
            """
            SELECT payload, years_of_experience
            FROM employees
            ORDER BY created_at DESC
            """
        ).fetchall()

    employees = []

    for row in rows:

        employee = json.loads(row["payload"])

        employee["years_of_experience"] = (
            row["years_of_experience"]
        )

        employees.append(employee)

    return employees


def delete_employee(employee_id: str) -> bool:

    with connection() as db:

        cursor = db.execute(
            """
            DELETE FROM employees
            WHERE id = ?
            """,
            (employee_id,),
        )

    return cursor.rowcount > 0


# ============================================================
# ROLES
# ============================================================

def save_role(name: str) -> None:

    if not name or not name.strip():
        return

    with connection() as db:

        db.execute(
            """
            INSERT OR IGNORE INTO roles(name)
            VALUES (?)
            """,
            (name.strip(),),
        )


def list_roles() -> list[str]:

    with connection() as db:

        rows = db.execute(
            """
            SELECT name
            FROM roles
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()

    return [
        row["name"]
        for row in rows
    ]


# ============================================================
# PLANS
# ============================================================

def save_plan(
    project_id: str,
    plan: dict[str, Any],
) -> None:

    if not project_id:
        raise ValueError("Project ID is required")

    if not plan:
        raise ValueError("Plan cannot be empty")

    plan_id = str(
        plan.get("plan_id")
        or uuid.uuid4()
    )

    generated_at = str(
        plan.get("generated_at")
        or datetime.now(timezone.utc).isoformat()
    )

    saved_plan = {
        **plan,
        "plan_id": plan_id,
        "project_id": project_id,
        "generated_at": generated_at,
    }

    with connection() as db:

        # Verify that the project exists before saving
        # the plan.
        project_row = db.execute(
            """
            SELECT payload
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

        if not project_row:
            raise ValueError(
                f"Cannot save plan. "
                f"Project '{project_id}' does not exist."
            )

        # Save/update current plan.
        db.execute(
            """
            INSERT INTO plans (
                project_id,
                payload,
                generated_at
            )
            VALUES (?, ?, ?)

            ON CONFLICT(project_id)
            DO UPDATE SET
                payload = excluded.payload,
                generated_at = excluded.generated_at
            """,
            (
                project_id,
                json.dumps(saved_plan),
                generated_at,
            ),
        )

        # Regenerating replaces the previous active plan for this project,
        # so it must not show up twice in "Generated Plans".
        db.execute(
            """
            UPDATE plan_history
            SET status = 'superseded'
            WHERE project_id = ?
              AND status = 'active'
            """,
            (project_id,),
        )

        # Save history.
        db.execute(
            """
            INSERT INTO plan_history (
                id,
                project_id,
                payload,
                generated_at,
                status
            )
            VALUES (?, ?, ?, ?, 'active')
            """,
            (
                plan_id,
                project_id,
                json.dumps(saved_plan),
                generated_at,
            ),
        )

        # Mark project as successfully generated.
        project = json.loads(
            project_row["payload"]
        )

        project["status"] = "generated"

        db.execute(
            """
            UPDATE projects
            SET payload = ?,
                status = 'generated'
            WHERE id = ?
            """,
            (
                json.dumps(project),
                project_id,
            ),
        )


def get_plan_by_id(
    plan_id: str,
) -> dict[str, Any] | None:

    with connection() as db:

        row = db.execute(
            """
            SELECT
                payload,
                status,
                archived_at
            FROM plan_history
            WHERE id = ?
            """,
            (plan_id,),
        ).fetchone()

    if not row:
        return None

    plan = json.loads(row["payload"])

    plan["status"] = row["status"]
    plan["archived_at"] = row["archived_at"]

    return plan


def get_current_plan(
    project_id: str,
) -> dict[str, Any] | None:

    with connection() as db:

        row = db.execute(
            """
            SELECT payload
            FROM plans
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()

    if not row:
        return None

    return json.loads(row["payload"])


# ============================================================
# ACTIVE PLANS
# ============================================================

def list_plans() -> list[dict[str, Any]]:
    """
    Fetch all active generated plans.
    """

    with connection() as db:

        rows = db.execute(
            """
            SELECT
                h.id,
                h.project_id,
                h.payload,
                h.generated_at,
                p.payload AS project_payload
            FROM plan_history h
            JOIN projects p
                ON p.id = h.project_id
            WHERE h.status = 'active'
            ORDER BY h.generated_at DESC
            """
        ).fetchall()

    plans = []

    for row in rows:

        plan = json.loads(row["payload"])
        project = json.loads(row["project_payload"])

        plans.append(
            {
                "id": row["id"],
                "project_id": row["project_id"],
                "project_name": project.get(
                    "name",
                    "Unknown Project",
                ),
                "generated_at": row["generated_at"],
                "tasks": plan.get("tasks", []),
                "completion_date": plan.get(
                    "completion_date"
                ),
                "deadline_at_risk": plan.get(
                    "deadline_at_risk",
                    False,
                ),
            }
        )

    return plans


# ============================================================
# ARCHIVED PLANS
# ============================================================

def list_archived_plans() -> list[dict[str, Any]]:
    """
    Fetch all archived plans.
    """

    with connection() as db:

        rows = db.execute(
            """
            SELECT
                h.id,
                h.project_id,
                h.payload,
                h.generated_at,
                h.archived_at,
                p.payload AS project_payload
            FROM plan_history h
            JOIN projects p
                ON p.id = h.project_id
            WHERE h.status = 'archived'
            ORDER BY h.archived_at DESC
            """
        ).fetchall()

    archived = []

    for row in rows:

        project = json.loads(
            row["project_payload"]
        )

        archived.append(
            {
                "id": row["id"],
                "project_id": row["project_id"],
                "project_name": project.get(
                    "name",
                    "Unknown Project",
                ),
                "generated_at": row["generated_at"],
                "archived_at": row["archived_at"],
            }
        )

    return archived


def archive_plan(plan_id: str) -> bool:
    """
    Move a plan to the archive.
    """

    archived_at = datetime.now(
        timezone.utc
    ).isoformat()

    with connection() as db:

        cursor = db.execute(
            """
            UPDATE plan_history
            SET status = 'archived',
                archived_at = ?
            WHERE id = ?
              AND status = 'active'
            """,
            (
                archived_at,
                plan_id,
            ),
        )

    return cursor.rowcount > 0

def restore_plan(plan_id: str) -> bool:
    """
    Move an archived plan back to the active list.
    """

    with connection() as db:

        cursor = db.execute(
            """
            UPDATE plan_history
            SET status = 'active',
                archived_at = NULL
            WHERE id = ?
              AND status = 'archived'
            """,
            (plan_id,),
        )

    return cursor.rowcount > 0


def delete_plan(plan_id: str) -> bool:
    """
    Permanently delete a plan (active or archived).

    The project itself is kept; if it no longer has any visible plan
    it returns to 'draft' so it can be regenerated.
    """

    with connection() as db:

        row = db.execute(
            """
            SELECT project_id
            FROM plan_history
            WHERE id = ?
            """,
            (plan_id,),
        ).fetchone()

        if not row:
            return False

        project_id = row["project_id"]

        db.execute(
            "DELETE FROM plan_history WHERE id = ?",
            (plan_id,),
        )

        # Drop the "current plan" copy if it is the one being deleted.
        current = db.execute(
            "SELECT payload FROM plans WHERE project_id = ?",
            (project_id,),
        ).fetchone()

        if current and json.loads(current["payload"]).get("plan_id") == plan_id:
            db.execute(
                "DELETE FROM plans WHERE project_id = ?",
                (project_id,),
            )

        remaining = db.execute(
            """
            SELECT 1
            FROM plan_history
            WHERE project_id = ?
              AND status IN ('active', 'archived')
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()

        if not remaining:
            project_row = db.execute(
                "SELECT payload FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()

            if project_row:
                project = json.loads(project_row["payload"])
                project["status"] = "draft"
                db.execute(
                    """
                    UPDATE projects
                    SET payload = ?, status = 'draft'
                    WHERE id = ?
                    """,
                    (json.dumps(project), project_id),
                )

    return True
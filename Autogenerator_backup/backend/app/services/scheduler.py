from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from math import floor
from typing import Any, cast

# FIXED: Safe date parser that handles None, "", and "None" strings
def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    val_str = str(value).strip()
    if val_str == "" or val_str.lower() == "none":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(val_str)
    except ValueError:
        return None

def _next_workday(day: date, weekdays: set[int], holidays: set[date]) -> date:
    while day.weekday() not in weekdays or day in holidays:
        day += timedelta(days=1)
    return day

def _phase_for_task(task: dict[str, Any]) -> str:
    text = f"{task.get('title', '')} {task.get('description', '')}".casefold()
    phases = [
        ("Discovery", ("requirement", "stakeholder", "analysis", "discovery")),
        ("Design", ("design", "wireframe", "prototype")),
        ("Integration", ("integration", "integrate")),
        ("Quality assurance", ("test", "qa", "acceptance", "verify")),
        ("Deployment", ("deploy", "release", "publish", "production")),
        ("Documentation", ("document", "readme", "runbook", "guide")),
    ]
    return next((name for name, keywords in phases if any(keyword in text for keyword in keywords)), "Implementation")

def _available_capacity_hours(
    employee: dict[str, Any],
    start: date,
    deadline: date,
    weekdays: set[int],
    holidays: set[date],
) -> float:
    leave = {d for val in employee.get("leave_dates", []) if (d := _as_date(val)) is not None}
    day = start
    available_days = 0
    while day <= deadline:
        if day.weekday() in weekdays and day not in holidays and day not in leave:
            available_days += 1
        day += timedelta(days=1)
    return available_days * float(employee.get("hours_per_day", 8.0))

def _allocate(
    employee: dict[str, Any],
    task: dict[str, Any],
    earliest: date,
    weekdays: set[int],
    holidays: set[date],
    bookings: dict[tuple[str, date], float],
) -> list[dict[str, Any]] | None:
    remaining_cents = round(float(task.get("remaining_hours", task["estimate_hours"])) * 100)
    day = earliest
    leave = {d for val in employee.get("leave_dates", []) if (d := _as_date(val)) is not None}
    employee_id = str(employee["id"])
    daily_hours = float(employee.get("hours_per_day", 8.0))
    
    available_days: list[tuple[date, int]] = []
    capacity_cents = 0

    for _ in range(730):
        if day.weekday() in weekdays and day not in holidays and day not in leave:
            booked_cents = round(bookings.get((employee_id, day), 0.0) * 100)
            daily_capacity_cents = round(daily_hours * 100)
            available_cents = max(0, daily_capacity_cents - booked_cents)
            
            if available_cents > 0:
                available_days.append((day, available_cents))
                capacity_cents += available_cents
                if capacity_cents >= remaining_cents:
                    break
        day += timedelta(days=1)
        
    if capacity_cents < remaining_cents:
        return None

    allocations: dict[date, int] = {}
    remaining = remaining_cents
    for workday, capacity in available_days:
        hours_cents = min(remaining, capacity)
        allocations[workday] = hours_cents
        remaining -= hours_cents
        if remaining == 0:
            break

    return [
        {"date": workday.isoformat(), "hours": hours_cents / 100}
        for workday, hours_cents in sorted(allocations.items())
        if hours_cents > 0
    ]

def generate_schedule(
    project: dict[str, Any],
    tasks: list[dict[str, Any]],
    employees: list[dict[str, Any]],
    holidays: list[str] | set[str] | None = None,
) -> dict[str, Any]:
    start = _as_date(project["start_date"])
    deadline = _as_date(project["deadline"])
    
    if not start or not deadline:
        raise ValueError("Project start_date and deadline must be valid dates.")

    weekdays = {int(day) for day in project.get("working_days", [0, 1, 2, 3, 4])}
    holiday_dates = {d for val in (holidays or []) if (d := _as_date(val)) is not None}
    warnings: list[dict[str, str]] = []
    task_by_id = {str(task["id"]): task for task in tasks}
    task_ids = list(task_by_id)
    
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    def order_key(task_id: str) -> tuple[int, str]:
        priority = str(task_by_id[task_id].get("priority", "Medium")).casefold()
        return priority_order.get(priority, 2), task_id

    missing_dependencies: dict[str, list[str]] = {}
    indegree = {task_id: 0 for task_id in task_ids}
    dependents: dict[str, list[str]] = defaultdict(list)

    for task_id, task in task_by_id.items():
        unknown = [str(dep) for dep in task.get("dependencies", []) if str(dep) not in task_by_id]
        if unknown:
            missing_dependencies[task_id] = unknown
            continue
        for dependency in task.get("dependencies", []):
            dependency_id = str(dependency)
            indegree[task_id] += 1
            dependents[dependency_id].append(task_id)

    ready = sorted(
        (task_id for task_id in task_ids if indegree[task_id] == 0 and task_id not in missing_dependencies),
        key=order_key,
    )
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for dependent in dependents[current]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
        ready.sort(key=order_key)

    unresolved = set(task_ids) - set(order)
    cyclic: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def find_cycles(task_id: str) -> None:
        if task_id in path:
            cyclic.update(path[path.index(task_id):])
            return
        if task_id in visited or task_id not in unresolved:
            return
        path.append(task_id)
        for dependency in task_by_id[task_id].get("dependencies", []):
            find_cycles(str(dependency))
        path.pop()
        visited.add(task_id)

    for task_id in unresolved:
        find_cycles(task_id)
    blocked = unresolved - cyclic - set(missing_dependencies)
    
    if cyclic:
        warnings.append({"type": "dependency_cycle", "message": f"Dependency cycle prevents scheduling: {', '.join(sorted(cyclic))}."})
    for task_id, dependencies in missing_dependencies.items():
        warnings.append({"type": "missing_dependency", "message": f"Task {task_id} references unknown dependencies: {', '.join(dependencies)}."})
    for task_id in sorted(blocked):
        warnings.append({"type": "dependency_blocked", "message": f"Task {task_id} is blocked by a prerequisite that could not be scheduled."})

    bookings: dict[tuple[str, date], float] = defaultdict(float)
    booked_hours: dict[str, float] = defaultdict(float)
    planned: dict[str, dict[str, Any]] = {}
    unassigned: list[str] = []
    blocked_by_unscheduled: set[str] = set()
    
    employee_capacity = {
        str(employee["id"]): _available_capacity_hours(employee, start, deadline, weekdays, holiday_dates)
        for employee in employees
    }

    for task_id in order:
        task = task_by_id[task_id]
        dependency_ids = [str(dep) for dep in task.get("dependencies", [])]
        
        if any(dependency_id not in planned or planned[dependency_id].get("end_date") is None for dependency_id in dependency_ids):
            unassigned.append(task_id)
            blocked_by_unscheduled.add(task_id)
            warnings.append({"type": "dependency_blocked", "message": f"Task {task_id} is blocked by a prerequisite that could not be scheduled."})
            continue
            
        estimate_hours = float(task["estimate_hours"])
        hours_completed = float(task.get("hours_completed", 0) or 0)
        remaining_hours = max(0, round(estimate_hours - hours_completed, 2))
        
        if task.get("status") == "completed":
            completed_date = _as_date(task.get("completed_at")) or _as_date(task.get("end_date")) or _as_date(task.get("start_date")) or start
            planned[task_id] = {
                **task,
                "id": task_id,
                "start_date": completed_date.isoformat(),
                "end_date": completed_date.isoformat(),
                "hours_completed": max(hours_completed, estimate_hours),
                "remaining_hours": 0,
                "phase": task.get("phase") or _phase_for_task(task),
                "uncertain": bool(task.get("uncertain", False)),
            }
            continue
            
        earliest = start
        if dependency_ids:
            valid_dates = []
            for dependency_id in dependency_ids:
                dep = planned.get(dependency_id, {})
                date_val = dep.get("completed_at") if dep.get("status") == "completed" else dep.get("end_date")
                parsed_date = _as_date(date_val)
                if parsed_date:
                    valid_dates.append(parsed_date)
            
            if valid_dates:
                latest_dependency = max(valid_dates)
                earliest = max(start, _next_workday(latest_dependency + timedelta(days=1), weekdays, holiday_dates))
            
        task_for_allocation = {**task, "remaining_hours": remaining_hours}
        
        required_roles = {role.strip().casefold() for role in task.get("required_roles", []) if role.strip()}
        if task.get("required_role"): 
            required_roles.add(str(task["required_role"]).strip().casefold())
        required_skills = {skill.strip().casefold() for skill in task.get("required_skills", []) if skill.strip()}
        
        selected_employee_id = str(task["assigned_employee_id"]) if task.get("assigned_employee_id") else None
        candidates: list[tuple[bool, date, float, int, int, float, str, dict[str, Any], list[dict[str, Any]]]] = []
        eligible_employees = 0

        for employee in employees:
            if selected_employee_id and str(employee["id"]) != selected_employee_id:
                continue
                
            employee_roles = {
                str(role).strip().casefold()
                for role in employee.get("roles", [employee.get("custom_role") or employee.get("role", "")])
                if str(role).strip()
            }
            if not employee_roles:
                employee_roles = {str(employee.get("custom_role") or employee.get("role", "")).casefold()}
                
            employee_skills = {str(skill).casefold() for skill in employee.get("skills", [])}
            
            matching_roles = employee_roles & required_roles
            role_match = not required_roles or bool(matching_roles)
            skill_match = not required_skills or required_skills.issubset(employee_skills)
            suitable = role_match and skill_match
            
            if not suitable:
                continue
                
            eligible_employees += 1
            allocation = _allocate(employee, task_for_allocation, earliest, weekdays, holiday_dates, bookings)
            
            if allocation:
                finish = _as_date(allocation[-1]["date"])
                # FIX: Cast to date to satisfy Pylance
                finish_date = cast(date, finish)
                
                skill_score = len(required_skills & employee_skills)
                employee_id = str(employee["id"])
                current_hours = booked_hours[employee_id]
                capacity_hours = employee_capacity[employee_id]
                
                projected_load = (current_hours + remaining_hours) / max(capacity_hours, remaining_hours, 1)
                experience_years = max(0, int(employee.get("years_of_experience", 0) or 0))
                priority_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(str(task.get("priority", "Medium")).casefold(), 2)
                
                primary_role = str(employee.get("custom_role") if employee.get("role") == "Other" else employee.get("role", "")).strip().casefold()
                primary_role_match = int(not required_roles or primary_role in required_roles)
                
                candidates.append((
                    finish_date > deadline, # FIX: Use casted date
                    finish_date,            # FIX: Use casted date
                    -(experience_years * priority_weight), 
                    -primary_role_match,
                    -skill_score,
                    projected_load if finish_date <= deadline else 0,
                    employee_id,
                    employee,
                    allocation,
                ))

        if not candidates:
            unassigned.append(task_id)
            if selected_employee_id:
                reason = "the selected employee is unavailable or does not match the task"
            elif not eligible_employees:
                reason = "no available employee matches the required role or skills"
            else:
                reason = "available team capacity"
            warnings.append({"type": "unassigned", "message": f"Task {task_id} could not be assigned because of {reason}."})
            continue

        _, _, _, _, _, _, employee_id, employee, allocation = min(candidates, key=lambda item: item[:7])
        
        daily_capacity = float(employee.get("hours_per_day", 8.0))
        allocation_details = []
        for item in allocation:
            workday = _as_date(item["date"])
            # FIX: Cast to date to satisfy Pylance
            workday_date = cast(date, workday)
            
            booking_key = (employee_id, workday_date)
            daily_total = round(bookings[booking_key] + item["hours"], 2)
            allocation_details.append({
                **item,
                "daily_total_hours": daily_total,
                "daily_capacity_hours": daily_capacity,
                "remaining_hours": round(max(0, daily_capacity - daily_total), 2),
            })
            bookings[booking_key] += item["hours"]
            booked_hours[employee_id] += item["hours"]
            
        task_plan = {
            **task,
            "id": task_id,
            "hours_completed": hours_completed,
            "remaining_hours": remaining_hours,
            "phase": _phase_for_task(task),
            "start_date": allocation[0]["date"],
            "end_date": allocation[-1]["date"],
            "assigned_employee_id": employee_id,
            "assigned_employee": employee["name"],
            "assigned_employee_experience": max(0, int(employee.get("years_of_experience", 0) or 0)),
            "assigned_employee_hours_per_day": daily_capacity,
            "assigned_role": next(
                (role for role in employee.get("roles", [employee.get("custom_role") or employee.get("role", "")]) if str(role).strip().casefold() in required_roles),
                employee.get("custom_role") or employee.get("role", ""),
            ),
            "allocation": allocation_details,
            "uncertain": bool(task.get("uncertain", False)),
        }
        planned[task_id] = task_plan
        
        if task_plan["uncertain"]:
            warnings.append({"type": "estimate_confirmation", "message": f"Confirm the estimate for task {task_id}."})
        
        # FIX: Safe parse and cast for end date
        end_date_check = _as_date(task_plan["end_date"])
        if end_date_check and end_date_check > deadline:
            warnings.append({"type": "deadline_risk", "message": f"Task {task_id} is projected to finish after the deadline."})

    unassigned.extend(sorted(cyclic | set(missing_dependencies) | blocked))
    unassigned = list(dict.fromkeys(unassigned))
    
    employee_by_id = {str(employee["id"]): employee for employee in employees}
    for task_plan in planned.values():
        employee_id = str(task_plan.get("assigned_employee_id", ""))
        employee = employee_by_id.get(employee_id)
        if employee is None:
            continue
        daily_capacity = float(employee.get("hours_per_day", 8.0))
        for allocation in task_plan.get("allocation", []):
            day = _as_date(allocation["date"])
            day_date = cast(date, day)
            
            daily_total = round(bookings[(employee_id, day_date)], 2)
            allocation.update({
                "daily_total_hours": daily_total,
                "daily_capacity_hours": daily_capacity,
                "remaining_hours": round(max(0, daily_capacity - daily_total), 2),
            })
            
    scheduled_tasks = sorted(planned.values(), key=lambda task: (task["start_date"], task["id"]))
    phase_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in scheduled_tasks:
        phase_groups[task["phase"]].append(task)
        
    phases = []
    for phase_name, phase_tasks in phase_groups.items():
        phase_start = min(task["start_date"] for task in phase_tasks)
        phase_end = max(task["end_date"] for task in phase_tasks)
        phases.append({
            "name": phase_name,
            "start_date": phase_start,
            "end_date": phase_end,
            "task_count": len(phase_tasks),
            "milestone": f"{phase_name} complete",
        })
    phases.sort(key=lambda phase: (phase["start_date"], phase["name"]))
    
    complete = len(planned) == len(task_by_id)
    completion_date = max((task["end_date"] for task in scheduled_tasks), default=None) if complete else None
    workload: dict[str, dict[str, float]] = defaultdict(dict)
    for (employee_id, day), hours in bookings.items():
        workload[employee_id][day.isoformat()] = round(hours, 2)

    # FIX: Safe parse and cast for completion date
    completion_date_check = _as_date(completion_date) if completion_date else None
    if completion_date_check and completion_date_check > deadline:
        warnings.append({"type": "deadline_risk", "message": "The current team capacity projects completion after the selected deadline."})
        
    return {
        "completion_date": completion_date,
        "deadline": deadline.isoformat(),
        "deadline_at_risk": completion_date_check is None or completion_date_check > deadline,
        "total_tasks": len(task_by_id),
        "scheduled_tasks": len(planned),
        "unassigned_tasks": unassigned,
        "blocked_tasks": sorted(cyclic | set(missing_dependencies) | blocked | blocked_by_unscheduled),
        "tasks": scheduled_tasks,
        "phases": phases,
        "milestones": [{"name": phase["milestone"], "date": phase["end_date"], "phase": phase["name"]} for phase in phases],
        "workload": dict(workload),
        "warnings": warnings,
        "assumptions": [
            "Each task is assigned to one employee and may span multiple working days.",
            "Dependent tasks start on the next available project working day after prerequisites finish.",
            "Major phases and milestones are keyword-grouped from reviewed tasks; no additional work is generated.",
            "The schedule is a deterministic capacity estimate, not a commitment.",
        ],
    }
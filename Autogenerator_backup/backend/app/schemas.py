from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Any, Optional
from pydantic import BaseModel, Field, model_validator, field_validator

# Must include every option offered by the New Plan form in App.jsx,
# otherwise POST /projects fails with a 422 for those choices.
ProjectType = Literal[
    "Web Application",
    "Mobile Application",
    "API",
    "API Development",
    "AI/ML",
    "AI/ML Project",
    "Testing",
    "QA Automation",
    "Cloud Migration",
    "Data Engineering",
    "Other",
]
Priority = Literal["Low", "Medium", "High", "Critical"]


# ==========================================
# 1. Project Schemas
# ==========================================

class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    project_type: ProjectType
    custom_project_type: str | None = Field(default=None, max_length=80)
    start_date: date
    deadline: date
    working_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], min_length=1)
    holidays: list[date] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_calendar(self) -> "ProjectCreate":
        if self.deadline < self.start_date:
            raise ValueError("Deadline must be on or after the start date.")
        if any(day < 0 or day > 6 for day in self.working_days):
            raise ValueError("Working days must use weekday numbers from 0 to 6.")
        if self.project_type == "Other" and not (self.custom_project_type or "").strip():
            raise ValueError("Enter a custom project type when Other is selected.")
        return self


# ==========================================
# 2. Employee Schemas
# ==========================================

class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    role: str = Field(min_length=2, max_length=80)
    additional_roles: list[str] = Field(default_factory=list) # ADDED
    custom_role: Optional[str] = Field(default=None, max_length=80) # ADDED
    hours_per_day: float = Field(gt=0, le=24)
    skills: list[str] = Field(default_factory=list)
    leave_dates: list[date] = Field(default_factory=list)
    
    years_of_experience: int = Field(default=0, ge=0, le=70)
    
    @field_validator("years_of_experience", mode="before")
    @classmethod
    def validate_experience(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            raise ValueError("Years of experience must be a valid number")


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    role: Optional[str] = Field(default=None, min_length=2, max_length=80)
    additional_roles: Optional[list[str]] = None # ADDED
    custom_role: Optional[str] = Field(default=None, max_length=80) # ADDED
    hours_per_day: Optional[float] = Field(default=None, gt=0, le=24)
    skills: Optional[list[str]] = None
    leave_dates: Optional[list[date]] = None
    
    years_of_experience: Optional[int] = Field(default=None, ge=0, le=70)

    @field_validator("years_of_experience", mode="before")
    @classmethod
    def validate_update_experience(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if v == "":
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            raise ValueError("Years of experience must be a valid number")


# ==========================================
# 3. Task & Plan Schemas
# ==========================================

class TaskItem(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=4000)
    estimate_hours: float = Field(gt=0, le=2000)
    required_roles: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    priority: Priority = "Medium"
    dependencies: list[str] = Field(default_factory=list)
    assigned_employee_id: str | None = None
    uncertain: bool = False
    status: str = "yet_to_start"

class TaskReview(BaseModel):
    tasks: list[TaskItem] = Field(max_length=500)


# ==========================================
# 4. Extra Schemas for Routers
# ==========================================

class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class HolidayCreate(BaseModel):
    date: date
    name: str = Field(min_length=2, max_length=100)


class PlanExportFormat(BaseModel):
    format: Literal["csv", "json"] = "json"
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
import pymupdf
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.repositories import sqlite_repo
from app.schemas import ProjectCreate, TaskReview, HolidayCreate
from app.services.pdf_parser import extract_candidate_tasks

router = APIRouter(prefix="/api/projects", tags=["Projects"])
MAX_PDF_BYTES = 10 * 1024 * 1024

def _project_or_404(project_id: str) -> dict[str, Any]:
    project = sqlite_repo.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project

@router.get("")
def list_projects() -> list[dict[str, Any]]:
    return sqlite_repo.list_projects()

@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(request: ProjectCreate) -> dict[str, Any]:
    project = request.model_dump(mode="json")
    project.update({"id": str(uuid.uuid4()), "tasks": [], "created_at": datetime.now(timezone.utc).isoformat()})
    sqlite_repo.save_project(project)
    return project

@router.get("/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    return _project_or_404(project_id)

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str) -> None:
    _project_or_404(project_id)
    sqlite_repo.delete_project(project_id)

@router.post("/{project_id}/upload")
async def upload_user_stories(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    project = _project_or_404(project_id)
    if not file.filename or not file.filename.casefold().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Upload a PDF file.")
    
    contents = await file.read(MAX_PDF_BYTES + 1)
    if len(contents) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF must be 10 MB or smaller.")
    if not contents.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF document.")
    
    try:
        document = pymupdf.open(stream=contents, filetype="pdf")
        if document.is_encrypted:
            raise HTTPException(status_code=422, detail="Password-protected PDFs are not supported.")
        text = "\n\n".join(page.get_text("text") for page in document)
        document.close()
    except Exception as error:
        raise HTTPException(status_code=422, detail="The PDF could not be read. Try exporting it again.") from error
        
    if not text.strip():
        raise HTTPException(status_code=422, detail="No selectable text found. Scanned PDFs require OCR.")
        
    extracted = extract_candidate_tasks(text)
    project["tasks"] = extracted["tasks"]
    project["source_file"] = file.filename[:180]
    sqlite_repo.save_project(project)
    return {**extracted, "source_file": project["source_file"], "text_preview": text[:4000]}

@router.put("/{project_id}/tasks")
def review_tasks(project_id: str, request: TaskReview) -> dict[str, Any]:
    project = _project_or_404(project_id)
    tasks = [task.model_dump(mode="json") for task in request.tasks]
    project["tasks"] = tasks
    sqlite_repo.save_project(project)
    return {"tasks": tasks, "count": len(tasks)}

@router.post("/{project_id}/holidays")
def add_holiday(project_id: str, request: HolidayCreate) -> dict[str, Any]:
    project = _project_or_404(project_id)
    holidays = project.setdefault("holidays", [])
    item = {"date": request.date.isoformat(), "name": request.name.strip()}
    if not any((holiday if isinstance(holiday, str) else holiday["date"]) == item["date"] for holiday in holidays):
        holidays.append(item)
        project["holidays"] = holidays
        sqlite_repo.save_project(project)
    return {"holidays": project["holidays"]}
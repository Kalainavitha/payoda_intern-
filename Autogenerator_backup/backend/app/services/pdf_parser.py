from __future__ import annotations

import re
from typing import Any

ROLE_KEYWORDS = {
    "Frontend Developer": ("frontend", "front-end", "react", "interface", "ui"),
    "Backend Developer": ("backend", "back-end", "api", "service", "endpoint"),
    "QA Engineer": ("test", "quality", "acceptance criteria", "verify"),
    "Automation Tester": ("automation", "automated", "selenium", "playwright"),
    "UI/UX Designer": ("design", "wireframe", "user experience", "prototype"),
    "DevOps Engineer": ("deploy", "pipeline", "infrastructure", "ci/cd"),
    "Database Administrator": ("database", "schema", "sql", "migration"),
    "AI/ML Engineer": ("model", "machine learning", "training", "inference"),
    "Mobile App Developer": ("mobile", "ios", "android", "app store"),
    "Security Engineer": ("security", "authentication", "authorization", "encryption"),
    "Business Analyst": ("requirement", "business rule", "stakeholder", "user story"),
}

def _paragraphs(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for raw_line in text.replace("\r", "").split("\n"):
        line = raw_line.strip()
        if not line:
            if current:
                blocks.append(" ".join(current))
                current = []
            continue
        starts_item = bool(re.match(r"^(?:[-*•]|\d+[.)])\s+", line))
        starts_story = bool(re.match(r"^(?:as a |user story\b|requirement\s*\d+)", line, re.I))
        if current and (starts_item or starts_story):
            blocks.append(" ".join(current))
            current = []
        current.append(re.sub(r"^(?:[-*•]|\d+[.)])\s+", "", line))
    if current:
        blocks.append(" ".join(current))
    return [re.sub(r"\s+", " ", block).strip() for block in blocks if len(block.strip()) >= 20]

def _roles_for(text: str) -> list[str]:
    lowered = text.casefold()
    return [role for role, keywords in ROLE_KEYWORDS.items() if any(re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in keywords)][:2]

def _is_requirement(text: str) -> bool:
    return bool(re.search(
        r"\b(as a |user story\b|requirement\b|acceptance criteria\b|given\b|when\b|then\b|shall\b|must\b|should\b|need(?:s)? to\b|want(?:s)? to\b|can\s+(?:view|create|edit|delete|access|manage|submit|receive|reset|review|export|upload|download)\b|allow(?:s)?\s+(?:the user|users|an? )|enable(?:s)?\s+(?:the user|users))",
        text,
        re.I,
    ))

def extract_candidate_tasks(text: str) -> dict[str, Any]:
    normalized = text[:200_000]
    candidates = [candidate for candidate in _paragraphs(normalized) if _is_requirement(candidate)]
    tasks: list[dict[str, Any]] = []
    orphaned_context = False
    
    for index, candidate in enumerate(candidates):
        if re.match(r"^(?:acceptance criteria|given\b|when\b|then\b)", candidate, re.I):
            if tasks:
                tasks[-1]["description"] += f"\n\n{candidate}"
            else:
                orphaned_context = True
            continue
            
        sentence = re.split(r"(?<=[.!?])\s+", candidate, maxsplit=1)[0]
        title = sentence[:120].strip(" .:-") or f"Requirement {index}"
        duration = re.search(r"\b(\d+(?:\.\d+)?)\s*(hours?|hrs?)\b", candidate, re.I)
        estimate_hours = float(duration.group(1)) if duration else 8.0
        roles = _roles_for(candidate)
        priority_match = re.search(r"\b(critical|high|medium|low)\s+priority\b", candidate, re.I)
        priority = priority_match.group(1).capitalize() if priority_match else "Medium"
        
        tasks.append({
            "id": f"T-{len(tasks) + 1:03d}",
            "title": title,
            "description": candidate,
            "estimate_hours": estimate_hours,
            "required_roles": roles,
            "required_skills": [],
            "priority": priority,
            "dependencies": [],
            "status": "yet_to_start", # Added for scheduler
            "uncertain": not bool(duration) or not bool(roles),
        })

    for task in tasks:
        inferred_roles = _roles_for(task["description"])
        task["required_roles"] = list(dict.fromkeys([*task["required_roles"], *inferred_roles]))[:2]
        references = re.findall(r"\bdepends?\s+on\s+(?:task\s+)?(?:T-)?(\d{1,3})\b", task["description"], re.I)
        task["dependencies"] = [f"T-{int(reference):03d}" for reference in references]
        task["dependencies"] = [dependency for dependency in task["dependencies"] if dependency != task["id"]]

    missing_information = []
    if not tasks:
        missing_information.append("No clear requirement paragraphs were found. Add or enter tasks manually.")
    if orphaned_context:
        missing_information.append("Some acceptance criteria had no preceding user story and were not converted into tasks.")
    if any(task["uncertain"] for task in tasks):
        missing_information.append("Some role or effort estimates are inferred and need review.")
        
    return {"tasks": tasks, "missing_information": missing_information, "text_characters": len(normalized)}
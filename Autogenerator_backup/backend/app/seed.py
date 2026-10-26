from __future__ import annotations

import argparse
import uuid

from backend.app import database


SAMPLE_EMPLOYEES = [
    {"name": "Jordan Lee", "role": "Frontend Developer", "hours_per_day": 6, "skills": ["React", "Accessibility"], "leave_dates": []},
    {"name": "Morgan Chen", "role": "Backend Developer", "hours_per_day": 6, "skills": ["Python", "FastAPI", "SQL"], "leave_dates": []},
    {"name": "Casey Patel", "role": "QA Engineer", "hours_per_day": 4, "skills": ["Test planning", "API testing"], "leave_dates": []},
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a small sample team into the local database.")
    parser.add_argument("--demo", action="store_true", help="Insert the sample employees.")
    args = parser.parse_args()
    database.initialize_database()
    if args.demo:
        for sample in SAMPLE_EMPLOYEES:
            employee = {**sample, "id": str(uuid.uuid4())}
            database.save_employee(employee)
            database.save_role(employee["role"])
        print("Sample team added. No sample projects or generated plans were created.")
    else:
        print("Database initialized. Use --demo to add sample employees.")


if __name__ == "__main__":
    main()

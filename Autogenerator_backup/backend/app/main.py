from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.repositories import sqlite_repo
from app.routers import projects, employees, roles, plans, plan_lists, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    sqlite_repo.initialize_database()
    yield


app = FastAPI(
    title="Auto Plan Generator API",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# CORS CONFIGURATION
# ---------------------------------------------------------
# React/Vite frontend can run on either 5173 or 5174.
# Both localhost and 127.0.0.1 are allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# API ROUTERS
# ---------------------------------------------------------
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(employees.router)
app.include_router(roles.router)
app.include_router(plans.router)
app.include_router(plan_lists.router)  # GET /api/plans, GET /api/archive, plan actions
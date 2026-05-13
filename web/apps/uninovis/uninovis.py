"""
UNINOVIS Admin — Central hub page for UNINOVIS management tools.
"""

import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

router = APIRouter(prefix="/uninovis", tags=["uninovis"])


@router.get("")
@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/services")
def services():
    return FileResponse(os.path.join(STATIC_DIR, "services.html"))

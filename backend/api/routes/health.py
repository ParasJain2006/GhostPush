from fastapi import APIRouter
from common.constants import API_VERSION

router = APIRouter()

@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "api_version": API_VERSION
    }

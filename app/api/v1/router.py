from fastapi import APIRouter

from app.api.v1 import payments

router = APIRouter(prefix="/api/v1")
router.include_router(payments.router)
from fastapi import Depends, FastAPI

from app.api.v1.router import router as v1_router
from app.dependencies import verify_api_key

app = FastAPI(
    title="Payments Processing Service",
    version="0.1.0",
)

app.include_router(v1_router)


@app.get("/health", dependencies=[Depends(verify_api_key)])
async def health() -> dict[str, str]:
    return {"status": "ok"}
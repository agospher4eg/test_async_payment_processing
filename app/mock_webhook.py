import logging
import os
import random

from fastapi import FastAPI, HTTPException, Request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mock.webhook")

app = FastAPI(title="Mock Webhook Receiver")

SUCCESS_RATE = float(os.getenv("MOCK_SUCCESS_RATE", "0.9"))


@app.post("/webhook")
async def receive_webhook(request: Request) -> dict:
    body = await request.json()
    success = random.random() < SUCCESS_RATE

    if success:
        logger.info("[200] %s", body)
        return {"status": "ok"}

    logger.warning("[500] %s", body)
    raise HTTPException(status_code=500, detail="simulated error")
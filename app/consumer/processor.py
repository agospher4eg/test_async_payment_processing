import asyncio
import random

from app.config import settings


async def process_payment(payment_id: str) -> bool:
    """
    Эмулирует обработку платежа через внешний шлюз.

    Возвращает True при успехе, False при ошибке.
    Длительность: PAYMENT_MIN_DELAY_SEC..PAYMENT_MAX_DELAY_SEC.
    Успех: PAYMENT_SUCCESS_RATE (по умолчанию 0.9).
    """
    delay = random.uniform(
        settings.PAYMENT_MIN_DELAY_SEC,
        settings.PAYMENT_MAX_DELAY_SEC,
    )
    await asyncio.sleep(delay)

    return random.random() < settings.PAYMENT_SUCCESS_RATE
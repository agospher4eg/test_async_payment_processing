import asyncio
import logging

import httpx

logger = logging.getLogger("consumer.webhook")

WEBHOOK_MAX_ATTEMPTS = 3
WEBHOOK_BASE_DELAY_SEC = 1.0
WEBHOOK_TIMEOUT_SEC = 10.0


async def send_webhook(
    webhook_url: str,
    payload: dict,
) -> bool:
    """
    Отправляет webhook на указанный URL.

    Retry: до WEBHOOK_MAX_ATTEMPTS попыток с экспоненциальной задержкой
    (1s, 2s, 4s). Возвращает True при успехе, False если все попытки провалились.
    """
    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SEC) as client:
        for attempt in range(1, WEBHOOK_MAX_ATTEMPTS + 1):
            try:
                response = await client.post(webhook_url, json=payload)
                if 200 <= response.status_code < 300:
                    logger.info(
                        "webhook delivered url=%s status=%s attempt=%s",
                        webhook_url,
                        response.status_code,
                        attempt,
                    )
                    return True

                logger.warning(
                    "webhook non-2xx url=%s status=%s attempt=%s",
                    webhook_url,
                    response.status_code,
                    attempt,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "webhook error url=%s attempt=%s error=%s",
                    webhook_url,
                    attempt,
                    exc,
                )

            if attempt < WEBHOOK_MAX_ATTEMPTS:
                delay = WEBHOOK_BASE_DELAY_SEC * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

    logger.error("webhook failed url=%s after %s attempts", webhook_url, WEBHOOK_MAX_ATTEMPTS)
    return False
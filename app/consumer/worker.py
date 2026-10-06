import logging
from datetime import datetime, timezone

from faststream import FastStream
from faststream.rabbit import RabbitMessage
from sqlalchemy import select

from app.config import settings
from app.consumer.processor import process_payment
from app.consumer.webhook import send_webhook
from app.db import SessionLocal
from app.models import Payment, PaymentStatus
from app.rabbit import (
    broker,
    payments_exchange,
    payments_new_queue,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("consumer.worker")

MAX_ATTEMPTS = settings.PAYMENT_MAX_ATTEMPTS

app = FastStream(broker)


@broker.subscriber(
    queue=payments_new_queue,
    exchange=payments_exchange,
)
async def handle_payment(payload: dict, message: RabbitMessage) -> None:
    payment_id = payload.get("payment_id")
    if not payment_id:
        logger.error("no payment_id in payload: %s", payload)
        await message.nack(requeue=False)
        return

    attempt = int(message.headers.get("x-attempts", 0)) + 1
    logger.info("processing payment id=%s attempt=%s", payment_id, attempt)

    async with SessionLocal() as session:
        payment = await session.scalar(
            select(Payment).where(Payment.id == payment_id)
        )
        if payment is None:
            logger.error("payment not found id=%s", payment_id)
            await message.ack()
            return

        # 1. Обработка — только если ещё pending
        if payment.status == PaymentStatus.pending:
            try:
                success = await process_payment(payment_id)
            except Exception as exc:
                logger.exception("processor error id=%s: %s", payment_id, exc)
                success = False

            payment.status = (
                PaymentStatus.succeeded if success else PaymentStatus.failed
            )
            payment.processed_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(
                "payment processed id=%s status=%s",
                payment_id,
                payment.status.value,
            )
        else:
            logger.info(
                "payment already processed id=%s status=%s, skipping processing",
                payment_id,
                payment.status.value,
            )

        webhook_url = payment.webhook_url
        webhook_payload = {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "amount": str(payment.amount),
            "currency": payment.currency.value,
            "processed_at": payment.processed_at.isoformat()
            if payment.processed_at
            else None,
        }

    delivered = await send_webhook(webhook_url, webhook_payload)

    if delivered:
        logger.info(
            "payment done id=%s status=%s",
            payment_id,
            webhook_payload["status"],
        )
        await message.ack()
        return

    # 3. Webhook не доставлен — retry или DLQ
    if attempt >= MAX_ATTEMPTS:
        logger.error(
            "payment id=%s exceeded max attempts=%s, sending to DLQ",
            payment_id,
            MAX_ATTEMPTS,
        )
        await message.nack(requeue=False)
        return

    logger.warning(
        "webhook failed, scheduling retry id=%s attempt=%s",
        payment_id,
        attempt,
    )
    await broker.publish(
        payload,
        exchange=payments_exchange,
        routing_key="payments.retry",
        headers={"x-attempts": attempt},
    )
    await message.ack()
import asyncio
import logging
from datetime import datetime, timezone

import aio_pika
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Outbox, OutboxStatus
from app.rabbit import broker, payments_exchange

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("outbox.publisher")

POLL_INTERVAL_SEC = 2
BATCH_SIZE = 100


async def declare_topology() -> None:
    """Объявляет exchange, очереди и биндинги в RabbitMQ."""
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()

        payments_ex = await channel.declare_exchange(
            "payments", aio_pika.ExchangeType.DIRECT, durable=True
        )
        payments_dlx = await channel.declare_exchange(
            "payments.dlx", aio_pika.ExchangeType.DIRECT, durable=True
        )

        q_new = await channel.declare_queue(
            "payments.new",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "payments.dlx",
                "x-dead-letter-routing-key": "payments.dlq",
            },
        )
        await q_new.bind(payments_ex, routing_key="payments.new")

        q_retry = await channel.declare_queue(
            "payments.retry",
            durable=True,
            arguments={
                "x-message-ttl": 10_000,
                "x-dead-letter-exchange": "payments",
                "x-dead-letter-routing-key": "payments.new",
            },
        )
        await q_retry.bind(payments_ex, routing_key="payments.retry")

        q_dlq = await channel.declare_queue("payments.dlq", durable=True)
        await q_dlq.bind(payments_dlx, routing_key="payments.dlq")

    logger.info("rabbitmq topology declared")


async def publish_pending() -> int:
    async with SessionLocal() as session:
        result = await session.scalars(
            select(Outbox)
            .where(Outbox.status == OutboxStatus.pending)
            .order_by(Outbox.created_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        events = list(result)

        if not events:
            return 0

        published_count = 0
        for event in events:
            try:
                await broker.publish(
                    message=event.payload,
                    exchange=payments_exchange,
                    routing_key="payments.new",
                )
                event.status = OutboxStatus.published
                event.published_at = datetime.now(timezone.utc)
                published_count += 1
                logger.info(
                    "published outbox id=%s type=%s", event.id, event.event_type
                )
            except Exception as exc:
                event.attempts += 1
                logger.exception(
                    "failed to publish outbox id=%s attempt=%s: %s",
                    event.id,
                    event.attempts,
                    exc,
                )

        await session.commit()
        return published_count


async def main() -> None:
    await declare_topology()
    await broker.start()
    logger.info("outbox publisher started")
    try:
        while True:
            try:
                published = await publish_pending()
                if published:
                    logger.info("published %s events", published)
            except Exception:
                logger.exception("publish loop error")
            await asyncio.sleep(POLL_INTERVAL_SEC)
    finally:
        await broker.close()
        logger.info("outbox publisher stopped")


if __name__ == "__main__":
    asyncio.run(main())
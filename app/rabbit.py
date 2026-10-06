from faststream.rabbit import (
    ExchangeType,
    RabbitBroker,
    RabbitExchange,
    RabbitQueue,
)

from app.config import settings

# ─── Exchanges ────────────────────────────────────────────────
payments_exchange = RabbitExchange(
    name="payments",
    type=ExchangeType.DIRECT,
    durable=True,
)

payments_dlx = RabbitExchange(
    name="payments.dlx",
    type=ExchangeType.DIRECT,
    durable=True,
)

# ─── Queues ───────────────────────────────────────────────────
payments_new_queue = RabbitQueue(
    name="payments.new",
    durable=True,
    routing_key="payments.new",
    arguments={
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": "payments.dlq",
    },
)

payments_retry_queue = RabbitQueue(
    name="payments.retry",
    durable=True,
    routing_key="payments.retry",
    arguments={
        "x-message-ttl": 10_000,
        "x-dead-letter-exchange": "payments",
        "x-dead-letter-routing-key": "payments.new",
    },
)

payments_dlq_queue = RabbitQueue(
    name="payments.dlq",
    durable=True,
    routing_key="payments.dlq",
)

# ─── Broker ───────────────────────────────────────────────────
broker = RabbitBroker(settings.rabbitmq_url)
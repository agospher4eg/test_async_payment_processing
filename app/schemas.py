import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models import Currency, PaymentStatus


class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    currency: Currency
    description: str = Field("", max_length=1000)
    meta: dict = Field(default_factory=dict)
    webhook_url: HttpUrl

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "amount": "100.50",
                "currency": "RUB",
                "description": "Оплата заказа №42",
                "meta": {"order_id": "42"},
                "webhook_url": "https://example.com/webhook",
            }
        }
    )


class PaymentResponse(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentDetail(BaseModel):
    id: uuid.UUID
    amount: Decimal
    currency: Currency
    description: str
    meta: dict
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
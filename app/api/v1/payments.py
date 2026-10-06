from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import verify_api_key
from app.models import Outbox, Payment, PaymentStatus
from app.schemas import PaymentCreate, PaymentDetail, PaymentResponse

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    dependencies=[Depends(verify_api_key)],
)



@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PaymentResponse,
)
async def create_payment(
    payload: PaymentCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentResponse:
    # 1. Проверяем идемпотентность: есть ли уже платёж с таким ключом
    existing = await session.scalar(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return PaymentResponse(
            payment_id=existing.id,
            status=existing.status,
            created_at=existing.created_at,
        )

    # 2. Создаём Payment + Outbox в одной транзакции (outbox pattern)
    payment = Payment(
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        meta=payload.meta,
        status=PaymentStatus.pending,
        idempotency_key=idempotency_key,
        webhook_url=str(payload.webhook_url),
    )
    session.add(payment)
    await session.flush()  # получаем payment.id без коммита

    outbox_event = Outbox(
        event_type="payment.created",
        payload={
            "payment_id": str(payment.id),
            "amount": str(payment.amount),
            "currency": payment.currency.value,
            "webhook_url": payment.webhook_url,
        },
    )
    session.add(outbox_event)

    try:
        await session.commit()
    except IntegrityError:
        # Гонка: другой запрос успел вставить тот же idempotency_key
        await session.rollback()
        existing = await session.scalar(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        if existing is None:
            raise
        return PaymentResponse(
            payment_id=existing.id,
            status=existing.status,
            created_at=existing.created_at,
        )

    await session.refresh(payment)

    return PaymentResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentDetail,
)
async def get_payment(
    payment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentDetail:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return PaymentDetail.model_validate(payment)
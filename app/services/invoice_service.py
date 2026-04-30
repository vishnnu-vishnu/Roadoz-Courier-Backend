import math
import uuid
import logging
from datetime import datetime, date

from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.franchise import Franchise
from app.models.order import Order
from app.models.invoice import Invoice, InvoiceOrder
from app.models.role import Role
from app.models.user_role import UserRole
from app.schemas.invoice import (
    InvoiceOut,
    InvoiceListResponse,
    InvoiceGenerateRequest,
)

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────


async def _get_caller_role_name(db: AsyncSession, user_id: str) -> str | None:
    row = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    r = row.scalar_one_or_none()
    return r.lower() if r else None


async def _resolve_franchise_id(db: AsyncSession, user: User) -> str | None:
    if user.franchise_id:
        return user.franchise_id
    result = await db.execute(select(Franchise).where(Franchise.user_id == user.id))
    franchise = result.scalar_one_or_none()
    return franchise.id if franchise else None


async def _generate_invoice_number(db: AsyncSession) -> str:
    count = (await db.execute(select(func.count()).select_from(Invoice))).scalar_one()
    return str(count + 1)


# ── Generate invoice (admin) ─────────────────────────────────────────────


async def generate_invoice(
    db: AsyncSession, data: InvoiceGenerateRequest
) -> InvoiceOut:
    # Validate franchise
    result = await db.execute(select(Franchise).where(Franchise.id == data.franchise_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")

    if data.period_start > data.period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_start must be before period_end",
        )

    # Find orders in the period that have NOT been invoiced yet
    period_start_dt = datetime.combine(data.period_start, datetime.min.time())
    period_end_dt = datetime.combine(data.period_end, datetime.max.time())

    orders_result = await db.execute(
        select(Order).where(
            and_(
                Order.franchise_id == data.franchise_id,
                Order.created_at >= period_start_dt,
                Order.created_at <= period_end_dt,
                Order.shipping_charge > 0,
                ~Order.id.in_(select(InvoiceOrder.order_id)),
            )
        )
    )
    orders = orders_result.scalars().all()

    if not orders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No uninvoiced orders with shipping charges found in this period",
        )

    subtotal = sum(float(o.shipping_charge) for o in orders)
    tax_amount = round(subtotal * data.tax_rate / 100, 2)
    total_amount = round(subtotal + tax_amount, 2)

    invoice_number = await _generate_invoice_number(db)

    description = data.description or (
        f"Services used From {data.period_start.strftime('%d %b %Y')} "
        f"To {data.period_end.strftime('%d %b %Y')}"
    )

    invoice = Invoice(
        id=str(uuid.uuid4()),
        invoice_number=invoice_number,
        franchise_id=data.franchise_id,
        description=description,
        period_start=data.period_start,
        period_end=data.period_end,
        subtotal=subtotal,
        tax_rate=data.tax_rate,
        tax_amount=tax_amount,
        total_amount=total_amount,
        orders_count=len(orders),
        status="issued",
    )
    db.add(invoice)
    await db.flush()

    for order in orders:
        io = InvoiceOrder(
            id=str(uuid.uuid4()),
            invoice_id=invoice.id,
            order_id=order.id,
            shipping_charge=float(order.shipping_charge),
        )
        db.add(io)

    await db.flush()
    await db.refresh(invoice)

    logger.info(
        f"Invoice generated: #{invoice_number}, franchise={data.franchise_id}, "
        f"subtotal={subtotal}, tax={tax_amount}, total={total_amount}, orders={len(orders)}"
    )
    return InvoiceOut.model_validate(invoice)


# ── List invoices ─────────────────────────────────────────────────────────


async def list_invoices(
    db: AsyncSession,
    current_user: User,
    page: int = 1,
    limit: int = 25,
    franchise_id: str | None = None,
) -> InvoiceListResponse:
    caller_role = await _get_caller_role_name(db, current_user.id)

    filters = []

    if caller_role == "super_admin":
        if franchise_id:
            filters.append(Invoice.franchise_id == franchise_id)
    else:
        fid = await _resolve_franchise_id(db, current_user)
        if not fid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No franchise linked to this user",
            )
        filters.append(Invoice.franchise_id == fid)

    query = select(Invoice).order_by(Invoice.created_at.desc())
    count_query = select(func.count()).select_from(Invoice)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * limit
    result = await db.execute(query.offset(offset).limit(limit))
    invoices = result.scalars().all()

    return InvoiceListResponse(
        items=[InvoiceOut.model_validate(i) for i in invoices],
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total > 0 else 0,
    )


# ── Get single invoice ───────────────────────────────────────────────────


async def get_invoice(
    db: AsyncSession, invoice_id: str, current_user: User
) -> InvoiceOut:
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    # Access control
    caller_role = await _get_caller_role_name(db, current_user.id)
    if caller_role != "super_admin":
        fid = await _resolve_franchise_id(db, current_user)
        if invoice.franchise_id != fid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return InvoiceOut.model_validate(invoice)


# ── Mark invoice as paid (admin) ─────────────────────────────────────────


async def mark_paid(
    db: AsyncSession, invoice_id: str
) -> InvoiceOut:
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    if invoice.status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already marked as paid",
        )

    invoice.status = "paid"
    await db.flush()
    await db.refresh(invoice)

    logger.info(f"Invoice marked paid: #{invoice.invoice_number}")
    return InvoiceOut.model_validate(invoice)

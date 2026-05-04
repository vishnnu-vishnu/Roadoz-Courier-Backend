import uuid
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.models.ticket import Ticket
from app.models.order import Order
from app.schemas.tickets import TicketCreate, TicketOut, TicketListResponse


async def create_ticket(
    db: AsyncSession,
    data: TicketCreate,
    current_user_id: str
) -> TicketOut:

    order = (
        await db.execute(select(Order).where(Order.id == data.order_id))
    ).scalar_one_or_none()

    if not order:
        raise ValueError("Order not found")

    ticket = Ticket(
        id=str(uuid.uuid4()),
        order_id=data.order_id,
        subject=data.subject,
        description=data.description,
        priority=data.priority or "medium",
        notify_email=data.notify_email,
        created_by=current_user_id,
    )

    db.add(ticket)
    await db.flush()
    await db.refresh(ticket)

    return TicketOut.model_validate(ticket)


async def list_tickets(
    db: AsyncSession,
    page: int = 1,
    limit: int = 10,
    status: Optional[str] = None,
    priority: Optional[str] = None,
):
    offset = (page - 1) * limit

    query = select(Ticket)

    if status:
        query = query.where(Ticket.status == status)

    if priority:
        query = query.where(Ticket.priority == priority)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(desc(Ticket.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    tickets = result.scalars().all()

    items = [TicketOut.model_validate(t) for t in tickets]

    return TicketListResponse(
        total=total,
        page=page,
        limit=limit,
        items=items
    )
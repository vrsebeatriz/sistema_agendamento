from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    appointment_id: int = Field(foreign_key="appointment.id", index=True)

    provider: str  # stripe | mercadopago | manual
    external_id: Optional[str] = None  # id do Stripe, por exemplo

    amount: float

    status: str = Field(default="pending", index=True)
    # pending | paid | failed | refunded

    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None

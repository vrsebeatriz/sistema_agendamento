from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Appointment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    client_id: int = Field(foreign_key="user.id", index=True)
    barber_id: int = Field(foreign_key="user.id", index=True)
    service_id: int = Field(foreign_key="service.id", index=True)

    appointment_time: datetime = Field(index=True)

    # SNAPSHOT FINANCEIRO
    service_name_snapshot: str
    service_price_snapshot: float
    service_duration_snapshot: int

    # STATUS DO AGENDAMENTO
    status: str = Field(default="pending", index=True)
    # pending | confirmed | canceled | completed | no_show

    # STATUS DO PAGAMENTO
    payment_status: str = Field(default="unpaid", index=True)
    # unpaid | paid | refunded

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    canceled_at: Optional[datetime] = Field(default=None, index=True)
    canceled_by: Optional[str] = None
    cancel_reason: Optional[str] = None

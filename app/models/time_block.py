from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class TimeBlock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    barber_id: int = Field(foreign_key="user.id", index=True)

    start_time: datetime = Field(index=True)
    end_time: datetime = Field(index=True)

    reason: str = "Bloqueio"

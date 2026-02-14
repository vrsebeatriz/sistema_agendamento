from typing import Optional
from sqlmodel import SQLModel, Field


class Service(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    name: str
    duration_minutes: int
    price: float
    active: bool = True

    barber_id: int = Field(foreign_key="user.id")

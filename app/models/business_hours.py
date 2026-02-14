from typing import Optional
from datetime import time
from sqlmodel import SQLModel, Field


class BusinessHours(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    barber_id: int = Field(foreign_key="user.id", index=True)

    # 0=segunda ... 6=domingo
    weekday: int = Field(index=True)

    is_closed: bool = False

    open_time: Optional[time] = None
    close_time: Optional[time] = None

    # opcional: intervalo de almoço
    lunch_start: Optional[time] = None
    lunch_end: Optional[time] = None

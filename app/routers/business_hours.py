from datetime import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.business_hours import BusinessHours
from app.models.user import User
from app.core.security import get_current_barber

router = APIRouter(prefix="/business-hours", tags=["business-hours"])


@router.get("/")
def list_business_hours(
    session: Session = Depends(get_session),
    current_barber: User = Depends(get_current_barber),
):
    return session.exec(
        select(BusinessHours).where(BusinessHours.barber_id == current_barber.id)
    ).all()


@router.put("/{weekday}")
def upsert_business_hours(
    weekday: int,
    payload: BusinessHours,
    session: Session = Depends(get_session),
    current_barber: User = Depends(get_current_barber),
):
    """
    weekday: 0=segunda ... 6=domingo
    """
    if weekday < 0 or weekday > 6:
        raise HTTPException(status_code=400, detail="weekday deve ser 0..6")

    # validações básicas
    if not payload.is_closed:
        if payload.open_time is None or payload.close_time is None:
            raise HTTPException(status_code=400, detail="open_time e close_time são obrigatórios quando is_closed=false")

        if payload.close_time <= payload.open_time:
            raise HTTPException(status_code=400, detail="close_time deve ser maior que open_time")

        if payload.lunch_start and payload.lunch_end:
            if payload.lunch_end <= payload.lunch_start:
                raise HTTPException(status_code=400, detail="lunch_end deve ser maior que lunch_start")

    existing = session.exec(
        select(BusinessHours).where(
            BusinessHours.barber_id == current_barber.id,
            BusinessHours.weekday == weekday,
        )
    ).first()

    if existing:
        existing.is_closed = payload.is_closed
        existing.open_time = payload.open_time
        existing.close_time = payload.close_time
        existing.lunch_start = payload.lunch_start
        existing.lunch_end = payload.lunch_end
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    new = BusinessHours(
        barber_id=current_barber.id,
        weekday=weekday,
        is_closed=payload.is_closed,
        open_time=payload.open_time,
        close_time=payload.close_time,
        lunch_start=payload.lunch_start,
        lunch_end=payload.lunch_end,
    )
    session.add(new)
    session.commit()
    session.refresh(new)
    return new

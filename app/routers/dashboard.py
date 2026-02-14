from datetime import date, datetime, timedelta, time
from collections import Counter

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.core.security import get_current_barber
from app.models.user import User
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.business_hours import BusinessHours


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _day_bounds(d: date):
    start = datetime.combine(d, time(0, 0))
    end = start + timedelta(days=1)
    return start, end


@router.get("/summary")
def dashboard_summary(
    day: date,
    session: Session = Depends(get_session),
    current_barber: User = Depends(get_current_barber),
):
    start, end = _day_bounds(day)

    appts = session.exec(
        select(Appointment).where(
            Appointment.barber_id == current_barber.id,
            Appointment.appointment_time >= start,
            Appointment.appointment_time < end,
        )
    ).all()

    # métricas
    total = len(appts)
    by_status = Counter([a.status for a in appts])

    # receita: só completed (produto real)
    revenue = 0.0
    minutes_completed = 0

    service_ids = [a.service_id for a in appts]
    services = session.exec(select(Service).where(Service.id.in_(service_ids))).all()
    service_map = {s.id: s for s in services}

    for a in appts:
        s = service_map.get(a.service_id)
        if not s:
            continue
        if a.status == "completed":
            revenue += float(s.price)
            minutes_completed += int(s.duration_minutes)

    # ocupação: compara minutos ocupados com expediente do dia (se houver)
    weekday = day.weekday()
    bh = session.exec(
        select(BusinessHours).where(
            BusinessHours.barber_id == current_barber.id,
            BusinessHours.weekday == weekday,
        )
    ).first()

    capacity_minutes = None
    occupancy = None

    if bh and (not bh.is_closed) and bh.open_time and bh.close_time:
        open_dt = datetime.combine(day, bh.open_time)
        close_dt = datetime.combine(day, bh.close_time)
        capacity_minutes = int((close_dt - open_dt).total_seconds() // 60)

        # tira almoço da capacidade
        if bh.lunch_start and bh.lunch_end:
            ls = datetime.combine(day, bh.lunch_start)
            le = datetime.combine(day, bh.lunch_end)
            capacity_minutes -= int((le - ls).total_seconds() // 60)

        if capacity_minutes > 0:
            occupancy = round((minutes_completed / capacity_minutes) * 100, 2)

    # top serviços (por quantidade de agendamentos do dia)
    top_counter = Counter(service_ids)
    top = []
    for sid, qty in top_counter.most_common(5):
        s = service_map.get(sid)
        if s:
            top.append({"service_id": sid, "name": s.name, "count": qty})

    return {
        "day": day.isoformat(),
        "barber_id": current_barber.id,
        "total_appointments": total,
        "status": dict(by_status),
        "revenue_completed": round(revenue, 2),
        "minutes_completed": minutes_completed,
        "capacity_minutes": capacity_minutes,
        "occupancy_percent": occupancy,
        "top_services": top,
    }

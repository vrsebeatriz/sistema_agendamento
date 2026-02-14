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

    total = len(appts)
    by_status = Counter([a.status for a in appts])

    revenue = 0.0
    minutes_completed = 0

    for a in appts:
        if a.status == "completed":
            revenue += float(a.service_price_snapshot or 0)
            minutes_completed += int(a.service_duration_snapshot or 0)

    # ocupação
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

        if bh.lunch_start and bh.lunch_end:
            ls = datetime.combine(day, bh.lunch_start)
            le = datetime.combine(day, bh.lunch_end)
            capacity_minutes -= int((le - ls).total_seconds() // 60)

        if capacity_minutes > 0:
            occupancy = round((minutes_completed / capacity_minutes) * 100, 2)

    # top serviços usando snapshot
    service_counter = Counter(
        [a.service_name_snapshot for a in appts if a.service_name_snapshot]
    )

    top = [
        {"name": name, "count": qty}
        for name, qty in service_counter.most_common(5)
    ]

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

@router.get("/monthly")
def monthly_dashboard(
    year: int,
    month: int,
    session: Session = Depends(get_session),
    current_barber: User = Depends(get_current_barber),
):
    from calendar import monthrange

    last_day = monthrange(year, month)[1]

    start = datetime(year, month, 1, 0, 0)
    end = datetime(year, month, last_day, 23, 59, 59)

    appts = session.exec(
        select(Appointment).where(
            Appointment.barber_id == current_barber.id,
            Appointment.appointment_time >= start,
            Appointment.appointment_time <= end,
        )
    ).all()

    total_completed = 0
    total_canceled = 0
    gross_revenue = 0.0
    paid_revenue = 0.0
    unpaid_revenue = 0.0

    service_counter = Counter()
    revenue_by_day = {}

    for appt in appts:

        if appt.status == "completed":
            total_completed += 1
            price = float(appt.service_price_snapshot or 0)
            gross_revenue += price

            service_counter[appt.service_name_snapshot] += 1

            day_key = appt.appointment_time.date().isoformat()
            revenue_by_day.setdefault(day_key, 0)
            revenue_by_day[day_key] += price

            if appt.payment_status == "paid":
                paid_revenue += price
            else:
                unpaid_revenue += price

        if appt.status == "canceled":
            total_canceled += 1

    ticket_medio = (
        round(gross_revenue / total_completed, 2)
        if total_completed > 0
        else 0
    )

    top_services = [
        {"service": name, "quantity": qty}
        for name, qty in service_counter.most_common(5)
    ]

    return {
        "period": {
            "year": year,
            "month": month,
        },
        "appointments_completed": total_completed,
        "appointments_canceled": total_canceled,
        "gross_revenue": round(gross_revenue, 2),
        "paid_revenue": round(paid_revenue, 2),
        "unpaid_revenue": round(unpaid_revenue, 2),
        "ticket_average": ticket_medio,
        "top_services": top_services,
        "revenue_by_day": revenue_by_day,
    }

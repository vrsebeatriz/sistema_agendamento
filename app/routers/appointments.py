from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.user import User
from app.models.business_hours import BusinessHours
from app.models.time_block import TimeBlock
from app.core.security import get_current_user


router = APIRouter(prefix="/appointments", tags=["appointments"])

SLOT_STEP = timedelta(minutes=15)
CANCEL_MIN_HOURS_BEFORE = 2


# =========================
# HELPERS
# =========================

def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and a_end > b_start


def _build_busy_intervals_for_day(
    session: Session,
    barber_id: int,
    day_start: datetime,
    day_end: datetime,
) -> List[Tuple[datetime, datetime]]:

    busy: List[Tuple[datetime, datetime]] = []

    appointments = session.exec(
        select(Appointment).where(
            Appointment.barber_id == barber_id,
            Appointment.appointment_time >= day_start,
            Appointment.appointment_time < day_end,
            Appointment.status != "canceled",
        )
    ).all()

    for appt in appointments:
        start = appt.appointment_time
        end = start + timedelta(minutes=appt.service_duration_snapshot or 0)
        busy.append((start, end))

    blocks = session.exec(
        select(TimeBlock).where(
            TimeBlock.barber_id == barber_id,
            TimeBlock.start_time < day_end,
            TimeBlock.end_time > day_start,
        )
    ).all()

    for b in blocks:
        busy.append((b.start_time, b.end_time))

    return busy


def _get_business_hours_for_day(session: Session, barber_id: int, day: date):
    return session.exec(
        select(BusinessHours).where(
            BusinessHours.barber_id == barber_id,
            BusinessHours.weekday == day.weekday(),
        )
    ).first()


# =========================
# CRIAR AGENDAMENTO
# =========================

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment: Appointment,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):

    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Apenas clientes podem agendar")

    service = session.get(Service, appointment.service_id)
    if not service or not service.active:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    barber_id = service.barber_id
    start_time = appointment.appointment_time
    end_time = start_time + timedelta(minutes=service.duration_minutes)

    hours = _get_business_hours_for_day(session, barber_id, start_time.date())
    if not hours or hours.is_closed or not hours.open_time or not hours.close_time:
        raise HTTPException(status_code=400, detail="Barbearia fechada nesse dia")

    day_start = datetime.combine(start_time.date(), hours.open_time)
    day_end = datetime.combine(start_time.date(), hours.close_time)

    if start_time < day_start or end_time > day_end:
        raise HTTPException(status_code=400, detail="Fora do horário de funcionamento")

    busy_intervals = _build_busy_intervals_for_day(session, barber_id, day_start, day_end)

    for b_start, b_end in busy_intervals:
        if _overlaps(start_time, end_time, b_start, b_end):
            raise HTTPException(status_code=400, detail="Horário indisponível")

    # 🔥 Dados forçados
    appointment.client_id = current_user.id
    appointment.barber_id = barber_id
    appointment.status = "pending"

    # 🔥 Snapshot financeiro
    appointment.service_name_snapshot = service.name
    appointment.service_price_snapshot = service.price
    appointment.service_duration_snapshot = service.duration_minutes

    appointment.payment_status = "unpaid"

    session.add(appointment)
    session.commit()
    session.refresh(appointment)
    return appointment


# =========================
# LISTAR AGENDAMENTOS
# =========================

@router.get("/")
def list_appointments(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):

    if current_user.role == "client":
        return session.exec(
            select(Appointment).where(Appointment.client_id == current_user.id)
        ).all()

    if current_user.role == "barber":
        return session.exec(
            select(Appointment).where(Appointment.barber_id == current_user.id)
        ).all()

    raise HTTPException(status_code=403, detail="Sem permissão")


# =========================
# CANCELAR
# =========================

@router.patch("/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: int,
    reason: str = "Cancelado",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):

    appt = session.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    if appt.status == "canceled":
        return appt

    is_client = current_user.role == "client" and appt.client_id == current_user.id
    is_barber = current_user.role == "barber" and appt.barber_id == current_user.id

    if not (is_client or is_barber):
        raise HTTPException(status_code=403, detail="Sem permissão")

    if is_client:
        now = datetime.utcnow()
        if appt.appointment_time - now < timedelta(hours=CANCEL_MIN_HOURS_BEFORE):
            raise HTTPException(
                status_code=400,
                detail=f"Cancelamento permitido apenas até {CANCEL_MIN_HOURS_BEFORE}h antes",
            )

    appt.status = "canceled"
    appt.canceled_at = datetime.utcnow()
    appt.canceled_by = "client" if is_client else "barber"
    appt.cancel_reason = reason

    session.add(appt)
    session.commit()
    session.refresh(appt)
    return appt


# =========================
# CONFIRMAR
# =========================

@router.patch("/{appointment_id}/confirm")
def confirm_appointment(
    appointment_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):

    if current_user.role != "barber":
        raise HTTPException(status_code=403, detail="Apenas barbeiro pode confirmar")

    appt = session.get(Appointment, appointment_id)
    if not appt or appt.barber_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")

    appt.status = "confirmed"
    session.commit()
    session.refresh(appt)
    return appt


# =========================
# FINALIZAR
# =========================

@router.patch("/{appointment_id}/complete")
def complete_appointment(
    appointment_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):

    if current_user.role != "barber":
        raise HTTPException(status_code=403, detail="Apenas barbeiro pode finalizar")

    appt = session.get(Appointment, appointment_id)
    if not appt or appt.barber_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")

    appt.status = "completed"
    session.commit()
    session.refresh(appt)
    return appt


# =========================
# MARCAR COMO PAGO
# =========================

@router.patch("/{appointment_id}/pay")
def mark_as_paid(
    appointment_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):

    if current_user.role != "barber":
        raise HTTPException(status_code=403, detail="Apenas barbeiro pode registrar pagamento")

    appt = session.get(Appointment, appointment_id)
    if not appt or appt.barber_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")

    if appt.payment_status == "paid":
        return appt

    appt.payment_status = "paid"

    session.commit()
    session.refresh(appt)
    return appt

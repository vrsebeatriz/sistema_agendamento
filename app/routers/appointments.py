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


# passo dos slots no calendário (pode virar config no banco depois)
SLOT_STEP = timedelta(minutes=15)

# regra de cancelamento para cliente
CANCEL_MIN_HOURS_BEFORE = 2  # cliente só cancela até 2h antes


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Retorna True se [a_start, a_end) sobrepõe [b_start, b_end)."""
    return a_start < b_end and a_end > b_start


def _build_busy_intervals_for_day(
    session: Session,
    barber_id: int,
    day_start: datetime,
    day_end: datetime,
) -> List[Tuple[datetime, datetime]]:
    """Monta intervalos ocupados no dia:
    - agendamentos existentes (considerando duração do serviço)
    - bloqueios (TimeBlock) que intersectam o dia
    Obs: ignora agendamentos cancelados.
    """
    busy: List[Tuple[datetime, datetime]] = []

    # 1) agendamentos do dia (ignora cancelados)
    appointments = session.exec(
        select(Appointment).where(
            Appointment.barber_id == barber_id,
            Appointment.appointment_time >= day_start,
            Appointment.appointment_time < day_end,
            Appointment.status != "canceled",
        )
    ).all()

    for appt in appointments:
        appt_service = session.get(Service, appt.service_id)
        if not appt_service:
            continue
        start = appt.appointment_time
        end = start + timedelta(minutes=appt_service.duration_minutes)
        busy.append((start, end))

    # 2) bloqueios (TimeBlock)
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


def _get_business_hours_for_day(
    session: Session,
    barber_id: int,
    day: date,
) -> BusinessHours | None:
    weekday = day.weekday()
    return session.exec(
        select(BusinessHours).where(
            BusinessHours.barber_id == barber_id,
            BusinessHours.weekday == weekday,
        )
    ).first()


# =========================
# CRIAR AGENDAMENTO (CLIENTE)
# =========================
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment: Appointment,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Somente cliente agenda
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas clientes podem criar agendamentos",
        )

    # Serviço precisa existir e estar ativo
    service = session.get(Service, appointment.service_id)
    if not service or not service.active:
        raise HTTPException(status_code=404, detail="Serviço não encontrado ou inativo")

    # Barber vem do serviço (cliente não escolhe)
    barber_id = service.barber_id

    start_time = appointment.appointment_time
    end_time = start_time + timedelta(minutes=service.duration_minutes)

    # Horário do dia vindo do banco
    hours = _get_business_hours_for_day(session, barber_id, start_time.date())
    if not hours or hours.is_closed or not hours.open_time or not hours.close_time:
        raise HTTPException(
            status_code=400,
            detail="Barbearia fechada ou sem horário configurado para esse dia",
        )

    day_start = datetime.combine(start_time.date(), hours.open_time)
    day_end = datetime.combine(start_time.date(), hours.close_time)

    # Regras: dentro do expediente?
    if start_time < day_start or end_time > day_end:
        raise HTTPException(status_code=400, detail="Fora do horário de funcionamento")

    # Regras: almoço (se configurado)
    if hours.lunch_start and hours.lunch_end:
        lunch_start_dt = datetime.combine(start_time.date(), hours.lunch_start)
        lunch_end_dt = datetime.combine(start_time.date(), hours.lunch_end)
        if _overlaps(start_time, end_time, lunch_start_dt, lunch_end_dt):
            raise HTTPException(status_code=400, detail="Horário indisponível (intervalo de almoço)")

    # Conflito com outros agendamentos e bloqueios (por duração)
    busy_intervals = _build_busy_intervals_for_day(session, barber_id, day_start, day_end)

    # inclui almoço como intervalo ocupado também
    if hours.lunch_start and hours.lunch_end:
        busy_intervals.append(
            (
                datetime.combine(start_time.date(), hours.lunch_start),
                datetime.combine(start_time.date(), hours.lunch_end),
            )
        )

    for b_start, b_end in busy_intervals:
        if _overlaps(start_time, end_time, b_start, b_end):
            raise HTTPException(status_code=400, detail="Horário indisponível")

    # Força dados sensíveis
    appointment.client_id = current_user.id
    appointment.barber_id = barber_id

    # status inicial
    appointment.status = "pending"

    session.add(appointment)
    session.commit()
    session.refresh(appointment)
    return appointment


# =========================
# LISTAR AGENDAMENTOS
# - cliente: só os próprios
# - barbeiro: só os da agenda dele
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
# CANCELAR AGENDAMENTO
# - cliente: somente se for dele e com antecedência (2h)
# - barbeiro: pode sempre (se for da agenda dele)
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

    is_client_owner = (current_user.role == "client" and appt.client_id == current_user.id)
    is_barber_owner = (current_user.role == "barber" and appt.barber_id == current_user.id)

    if not (is_client_owner or is_barber_owner):
        raise HTTPException(status_code=403, detail="Sem permissão")

    # regra: cliente só pode cancelar até X horas antes
    if is_client_owner:
        now = datetime.utcnow()
        if appt.appointment_time - now < timedelta(hours=CANCEL_MIN_HOURS_BEFORE):
            raise HTTPException(
                status_code=400,
                detail=f"Cliente só pode cancelar com pelo menos {CANCEL_MIN_HOURS_BEFORE}h de antecedência",
            )

    appt.status = "canceled"
    appt.canceled_at = datetime.utcnow()
    appt.canceled_by = "client" if is_client_owner else "barber"
    appt.cancel_reason = reason

    session.add(appt)
    session.commit()
    session.refresh(appt)
    return appt


# =========================
# CONFIRMAR (BARBEIRO)
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
    if not appt:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    if appt.barber_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")

    if appt.status in ("canceled", "completed"):
        raise HTTPException(status_code=400, detail="Não é possível confirmar nesse status")

    appt.status = "confirmed"
    session.add(appt)
    session.commit()
    session.refresh(appt)
    return appt


# =========================
# FINALIZAR (BARBEIRO)
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
    if not appt:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    if appt.barber_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")

    if appt.status in ("canceled", "completed"):
        raise HTTPException(status_code=400, detail="Não é possível finalizar nesse status")

    appt.status = "completed"
    session.add(appt)
    session.commit()
    session.refresh(appt)
    return appt


# =========================
# HORÁRIOS DISPONÍVEIS (dia + serviço)
# GET /appointments/available?service_id=1&day=2026-02-14
# =========================
@router.get("/available")
def get_available_slots(
    service_id: int,
    day: date,
    session: Session = Depends(get_session),
) -> Dict:
    service = session.get(Service, service_id)
    if not service or not service.active:
        raise HTTPException(status_code=404, detail="Serviço não encontrado ou inativo")

    barber_id = service.barber_id
    duration = timedelta(minutes=service.duration_minutes)

    hours = _get_business_hours_for_day(session, barber_id, day)
    if not hours or hours.is_closed or not hours.open_time or not hours.close_time:
        return {
            "service_id": service_id,
            "day": day.isoformat(),
            "is_closed": True,
            "reason": "Sem horário configurado ou fechado",
            "slots": [],
        }

    day_start = datetime.combine(day, hours.open_time)
    day_end = datetime.combine(day, hours.close_time)

    # intervalos ocupados por agendamentos (não cancelados) + bloqueios
    busy_intervals = _build_busy_intervals_for_day(session, barber_id, day_start, day_end)

    # almoço
    lunch_break = None
    if hours.lunch_start and hours.lunch_end:
        lunch_start_dt = datetime.combine(day, hours.lunch_start)
        lunch_end_dt = datetime.combine(day, hours.lunch_end)
        busy_intervals.append((lunch_start_dt, lunch_end_dt))
        lunch_break = {"start": hours.lunch_start.isoformat(), "end": hours.lunch_end.isoformat()}

    def conflicts(start: datetime, end: datetime) -> bool:
        for b_start, b_end in busy_intervals:
            if _overlaps(start, end, b_start, b_end):
                return True
        return False

    slots: List[Dict[str, str]] = []
    current = day_start

    while current + duration <= day_end:
        slot_start = current
        slot_end = current + duration

        if not conflicts(slot_start, slot_end):
            slots.append({"start": slot_start.isoformat(), "end": slot_end.isoformat()})

        current += SLOT_STEP

    return {
        "service_id": service_id,
        "day": day.isoformat(),
        "is_closed": False,
        "barber_id": barber_id,
        "duration_minutes": service.duration_minutes,
        "slot_step_minutes": int(SLOT_STEP.total_seconds() // 60),
        "business_hours": {
            "weekday": day.weekday(),
            "open": hours.open_time.isoformat(),
            "close": hours.close_time.isoformat(),
        },
        "lunch_break": lunch_break,
        "slots": slots,
    }

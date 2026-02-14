from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.payment import Payment
from app.models.appointment import Appointment
from app.models.user import User
from app.core.security import get_current_user


router = APIRouter(prefix="/payments", tags=["payments"])


# =========================
# CRIAR PAGAMENTO (simulado)
# =========================
@router.post("/create/{appointment_id}")
def create_payment(
    appointment_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):

    appt = session.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    if appt.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")

    if appt.status != "completed":
        raise HTTPException(status_code=400, detail="Só é possível pagar após conclusão")

    payment = Payment(
        appointment_id=appointment_id,
        provider="manual",
        amount=appt.service_price_snapshot or 0,
        status="pending",
    )

    session.add(payment)
    session.commit()
    session.refresh(payment)

    return payment


# =========================
# CONFIRMAR PAGAMENTO (simulado)
# =========================
@router.patch("/{payment_id}/confirm")
def confirm_payment(
    payment_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):

    payment = session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    appt = session.get(Appointment, payment.appointment_id)

    if current_user.role != "barber":
        raise HTTPException(status_code=403, detail="Apenas barbeiro pode confirmar pagamento")

    payment.status = "paid"
    payment.paid_at = datetime.utcnow()

    # Atualiza appointment também
    appt.payment_status = "paid"

    session.add(payment)
    session.add(appt)
    session.commit()

    return payment

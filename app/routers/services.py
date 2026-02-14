from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.service import Service
from app.models.user import User
from app.core.security import get_current_barber


router = APIRouter(
    prefix="/services",
    tags=["services"]
)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_service(
    service: Service,
    session: Session = Depends(get_session),
    current_barber: User = Depends(get_current_barber),
):
    service.barber_id = current_barber.id

    session.add(service)
    session.commit()
    session.refresh(service)

    return service


@router.get("/")
def list_my_services(
    session: Session = Depends(get_session),
    current_barber: User = Depends(get_current_barber),
):
    services = session.exec(
        select(Service).where(Service.barber_id == current_barber.id)
    ).all()

    return services

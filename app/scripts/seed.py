from datetime import time, datetime, timedelta
from sqlmodel import Session, select

from app.database import engine
from app.models.user import User
from app.models.service import Service
from app.models.business_hours import BusinessHours
from app.models.time_block import TimeBlock


BARBER_EMAIL = "barbeiro@gmail.com" 


def main():
    with Session(engine) as session:
        # 1) pegar o barbeiro pelo email
        barber = session.exec(select(User).where(User.email == BARBER_EMAIL)).first()
        if not barber:
            raise RuntimeError(f"Não achei barbeiro com email {BARBER_EMAIL}. Crie um user role='barber' antes.")

        if barber.role != "barber":
            raise RuntimeError(f"Usuário {BARBER_EMAIL} existe mas role != 'barber'")

        # 2) criar/atualizar horários (seg-sáb aberto, domingo fechado)
        defaults = {
            0: dict(is_closed=False, open_time=time(8, 0), close_time=time(20, 0), lunch_start=None, lunch_end=None),
            1: dict(is_closed=False, open_time=time(8, 0), close_time=time(20, 0), lunch_start=None, lunch_end=None),
            2: dict(is_closed=False, open_time=time(8, 0), close_time=time(20, 0), lunch_start=None, lunch_end=None),
            3: dict(is_closed=False, open_time=time(8, 0), close_time=time(20, 0), lunch_start=None, lunch_end=None),
            4: dict(is_closed=False, open_time=time(8, 0), close_time=time(20, 0), lunch_start=None, lunch_end=None),
            5: dict(is_closed=False, open_time=time(8, 0), close_time=time(20, 0), lunch_start=None, lunch_end=None),
            6: dict(is_closed=True, open_time=None, close_time=None, lunch_start=None, lunch_end=None),
        }

        for weekday, cfg in defaults.items():
            row = session.exec(
                select(BusinessHours).where(
                    BusinessHours.barber_id == barber.id,
                    BusinessHours.weekday == weekday,
                )
            ).first()

            if row:
                row.is_closed = cfg["is_closed"]
                row.open_time = cfg["open_time"]
                row.close_time = cfg["close_time"]
                row.lunch_start = cfg["lunch_start"]
                row.lunch_end = cfg["lunch_end"]
                session.add(row)
            else:
                session.add(
                    BusinessHours(
                        barber_id=barber.id,
                        weekday=weekday,
                        is_closed=cfg["is_closed"],
                        open_time=cfg["open_time"],
                        close_time=cfg["close_time"],
                        lunch_start=cfg["lunch_start"],
                        lunch_end=cfg["lunch_end"],
                    )
                )

        # 3) criar serviços de teste (se não existir)
        existing_service = session.exec(
            select(Service).where(Service.barber_id == barber.id)
        ).first()

        if not existing_service:
            session.add_all(
                [
                    Service(name="Corte", duration_minutes=30, price=40.0, active=True, barber_id=barber.id),
                    Service(name="Barba", duration_minutes=20, price=30.0, active=True, barber_id=barber.id),
                    Service(name="Corte + Barba", duration_minutes=50, price=65.0, active=True, barber_id=barber.id),
                ]
            )

        # 4) criar um bloqueio de exemplo (opcional) - amanhã 15:00-16:00
        # comente se não quiser
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        block_start = datetime.combine(tomorrow, time(15, 0))
        block_end = datetime.combine(tomorrow, time(16, 0))

        exists_block = session.exec(
            select(TimeBlock).where(
                TimeBlock.barber_id == barber.id,
                TimeBlock.start_time == block_start,
                TimeBlock.end_time == block_end,
            )
        ).first()

        if not exists_block:
            session.add(TimeBlock(barber_id=barber.id, start_time=block_start, end_time=block_end, reason="Teste"))

        session.commit()

        print("✅ Seed concluído!")
        print(f"Barber: {barber.id} ({barber.email})")
        print("Horários: seg-sáb 09-18 almoço 12-13; domingo fechado")
        print("Serviços: Corte/Barba/Corte+Barba (se não existiam)")
        print("Bloqueio: amanhã 15:00-16:00 (se não existia)")


if __name__ == "__main__":
    main()

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.time_block import TimeBlock
from app.models.user import User
from app.core.security import get_current_barber

router = APIRouter(prefix="/time-blocks", tags=["time-blocks"])


@router.get("/")
def list_time_blocks(
    session: Session = Depends(get_session),
    current_barber: User = Depends(get_current_barber),
):
    return session.exec(
        select(TimeBlock).where(TimeBlock.barber_id == current_barber.id)
    ).all()


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_time_block(
    block: TimeBlock,
    session: Session = Depends(get_session),
    current_barber: User = Depends(get_current_barber),
):
    if block.end_time <= block.start_time:
        raise HTTPException(status_code=400, detail="end_time deve ser maior que start_time")

    # força ownership
    block.barber_id = current_barber.id

    session.add(block)
    session.commit()
    session.refresh(block)
    return block


@router.delete("/{block_id}")
def delete_time_block(
    block_id: int,
    session: Session = Depends(get_session),
    current_barber: User = Depends(get_current_barber),
):
    block = session.get(TimeBlock, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Bloqueio não encontrado")

    if block.barber_id != current_barber.id:
        raise HTTPException(status_code=403, detail="Sem permissão")

    session.delete(block)
    session.commit()
    return {"message": "Bloqueio removido"}

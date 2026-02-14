from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User, UserCreate
from app.core.security import get_password_hash

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/")
def create_user(user: UserCreate, session: Session = Depends(get_session)):

    existing_user = session.exec(
        select(User).where(User.email == user.email)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    hashed_password = get_password_hash(user.password)

    db_user = User(
        name=user.name,
        email=user.email,
        password_hash=hashed_password,
        role=user.role
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return {
    "id": db_user.id,
    "name": db_user.name,
    "email": db_user.email
}


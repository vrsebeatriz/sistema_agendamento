from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from app.database import get_session
from app.models.user import User


# =========================
# CONFIGURAÇÕES JWT
# =========================

SECRET_KEY = "1975beatriz1975"  # depois mover para .env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# =========================
# HASH DE SENHA
# =========================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# =========================
# TOKEN JWT
# =========================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# =========================
# USUÁRIO AUTENTICADO
# =========================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")

        if email is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = session.exec(
        select(User).where(User.email == email)
    ).first()

    if user is None:
        raise credentials_exception

    return user


# =========================
# SOMENTE BARBEIRO
# =========================

def get_current_barber(
    current_user: User = Depends(get_current_user),
) -> User:

    if current_user.role != "barber":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas barbeiros podem acessar esta rota"
        )

    return current_user


# =========================
# SOMENTE CLIENTE
# =========================

def get_current_client(
    current_user: User = Depends(get_current_user),
) -> User:

    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas clientes podem acessar esta rota"
        )

    return current_user

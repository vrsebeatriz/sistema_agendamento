from typing import Optional
from sqlmodel import SQLModel, Field


class UserBase(SQLModel):
    name: str
    email: str = Field(index=True, unique=True)
    role: str  # "barber" ou "client"


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str


class UserCreate(UserBase):
    password: str

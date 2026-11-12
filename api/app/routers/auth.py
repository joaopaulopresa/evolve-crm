from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_token, current_user, hash_password, require_admin, verify_password
from app.db import get_session
from app.models import User
from app.schemas import LoginIn, LoginOut, UserIn, UserOut

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login", response_model=LoginOut)
def login(payload: LoginIn, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong e-mail or password")
    return {"access_token": create_token(user), "user": user}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(session: Session = Depends(get_session), _: User = Depends(current_user)):
    return session.scalars(select(User).where(User.is_active).order_by(User.name)).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserIn, session: Session = Depends(get_session), _: User = Depends(require_admin)
):
    email = payload.email.lower()
    if session.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this e-mail already exists")
    user = User(
        email=email,
        name=payload.name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    return user

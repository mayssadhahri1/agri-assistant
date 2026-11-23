from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginIn, RegisterIn, TokenOut, UserOut, UserUpdate
from ..security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    conditions = []
    if data.email:
        conditions.append(User.email == data.email)
    if data.telephone:
        conditions.append(User.telephone == data.telephone)
    if db.scalar(select(User).where(or_(*conditions))):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email ou téléphone déjà utilisé")

    user = User(
        nom=data.nom,
        email=data.email,
        telephone=data.telephone,
        password_hash=hash_password(data.password),
        langue=data.langue,
        role="agriculteur",  # les rôles expert/admin sont attribués par un admin
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(
        select(User).where(or_(User.email == data.identifiant, User.telephone == data.identifiant))
    )
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants incorrects")
    if not user.actif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Compte désactivé")
    return TokenOut(access_token=create_token(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user

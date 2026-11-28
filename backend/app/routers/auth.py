from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import InscriptionOut, LoginJSON, Token, UserCreate, UserOut, normaliser_telephone
from ..security import create_access_token, get_current_user, hash_password, verify_password
from ..services.emails import notifier_admins_inscription

router = APIRouter(prefix="/auth", tags=["Authentification"])


def _find_by_identifiant(db: Session, identifiant: str) -> User | None:
    """L'identifiant peut être un email ou un numéro de téléphone."""
    ident = identifiant.strip()
    if "@" in ident:
        return db.scalar(select(User).where(User.email == ident.lower()))
    return db.scalar(select(User).where(User.telephone == normaliser_telephone(ident)))


def _authenticate(db: Session, identifiant: str, password: str) -> User:
    user = _find_by_identifiant(db, identifiant)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect",
        )
    # On vérifie le statut APRÈS le mot de passe : un inconnu n'apprend rien sur le compte
    if user.statut == "en_attente":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte est en attente de validation par un administrateur",
        )
    if user.statut == "refuse":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre demande d'inscription a été refusée par un administrateur",
        )
    if not user.actif:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")
    return user


def _token_response(user: User) -> Token:
    return Token(access_token=create_access_token(user), user=user)


@router.post("/register", response_model=InscriptionOut, status_code=201)
def register(data: UserCreate, request: Request, taches: BackgroundTasks, db: Session = Depends(get_db)):
    """Crée un compte **en attente** : les administrateurs reçoivent un email avec
    les boutons Accepter / Refuser."""
    conditions = []
    if data.email:
        conditions.append(User.email == data.email)
    if data.telephone:
        conditions.append(User.telephone == data.telephone)

    existing = db.scalar(select(User).where(or_(*conditions)))
    if existing:
        if data.email and existing.email == data.email:
            raise HTTPException(status_code=409, detail="Cet email est déjà utilisé")
        raise HTTPException(status_code=409, detail="Ce téléphone est déjà utilisé")

    user = User(
        nom=data.nom,
        email=data.email,
        telephone=data.telephone,
        password_hash=hash_password(data.password),
        role=data.role,
        langue=data.langue,
        statut="en_attente",      # le compte attend la validation de l'admin
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email ou téléphone déjà utilisé")
    db.refresh(user)
    # Email aux admins en arrière-plan (la réponse n'attend pas l'envoi)
    taches.add_task(notifier_admins_inscription, user.id, str(request.base_url))
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login par formulaire (bouton Authorize de Swagger). `username` = email ou téléphone."""
    return _token_response(_authenticate(db, form.username, form.password))


@router.post("/login/json", response_model=Token)
def login_json(data: LoginJSON, db: Session = Depends(get_db)):
    """Login en JSON (frontend React / Vue / mobile)."""
    return _token_response(_authenticate(db, data.identifiant, data.password))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
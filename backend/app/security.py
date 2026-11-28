from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > 72:          # bcrypt refuse > 72 octets
        return False
    try:
        return bcrypt.checkpw(raw, hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user.id), "role": user.role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


RESET_TYPE = "reset_mot_de_passe"
RESET_MINUTES = 60


def create_reset_token(user: User) -> str:
    """Lien « mot de passe oublié » valable 1 h. Il contient un bout du hash actuel :
    dès que le mot de passe change, l'ancien lien ne marche plus (usage unique)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_MINUTES)
    payload = {"type": RESET_TYPE, "sub": str(user.id), "h": user.password_hash[-12:], "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def lire_reset_token(token: str, db: Session) -> User:
    """Renvoie l'utilisateur du lien, ou lève une HTTPException claire."""
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Ce lien a expiré : refaites une demande")
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Lien invalide")
    if data.get("type") != RESET_TYPE:
        raise HTTPException(status_code=400, detail="Lien invalide")
    user = db.get(User, int(data["sub"]))
    if user is None or user.password_hash[-12:] != data.get("h"):
        raise HTTPException(status_code=400, detail="Ce lien a déjà été utilisé")
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise error

    user = db.get(User, user_id)
    # Un compte désactivé ou non validé par l'admin ne peut plus utiliser son token
    if user is None or not user.actif or user.statut != "valide":
        raise error
    return user


def require_roles(*roles: str):
    """Ex : Depends(require_roles("expert", "admin"))"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
        return user

    return checker
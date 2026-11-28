"""Routes réservées à l'administrateur : validation des comptes."""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Feedback, Message, Parcelle, Photo, User
from ..schemas import (
    StatsAdmin, StatsComptes, StatsParcelles, StatsPhotos, StatsQuestions, StatsSatisfaction, StatutCompte, UserOut,
)
from ..security import require_roles
from ..services.emails import notifier_client_decision

# Toutes les routes de ce fichier exigent un token d'un compte "admin"
router = APIRouter(prefix="/admin", tags=["Administration"])
admin_requis = require_roles("admin")


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    return user


def appliquer_decision(db: Session, admin: User, user: User, nouveau_statut: str) -> User:
    """Valide ou refuse un compte. Utilisé par Swagger ET par les boutons de l'email."""
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier votre propre compte")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Impossible de modifier un autre administrateur")
    user.statut = nouveau_statut
    user.valide_par = admin.id
    user.valide_le = datetime.now()
    db.commit()
    db.refresh(user)
    return user


def _decider(db: Session, admin: User, user_id: int, nouveau_statut: str, taches: BackgroundTasks) -> User:
    user = appliquer_decision(db, admin, _get_user(db, user_id), nouveau_statut)
    # Email à la personne pour la prévenir (en arrière-plan)
    taches.add_task(notifier_client_decision, user.id)
    return user


@router.get("/users", response_model=list[UserOut])
def lister_comptes(
    statut: StatutCompte | None = Query(default=None, description="Filtrer : en_attente, valide ou refuse"),
    db: Session = Depends(get_db),
    admin: User = Depends(admin_requis),
):
    """Liste des comptes (les plus récents d'abord). Mettre `statut=en_attente` pour voir les demandes."""
    query = select(User).order_by(User.created_at.desc(), User.id.desc())
    if statut:
        query = query.where(User.statut == statut)
    return db.scalars(query).all()


@router.get("/users/{user_id}", response_model=UserOut)
def voir_compte(user_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_requis)):
    return _get_user(db, user_id)


@router.patch("/users/{user_id}/valider", response_model=UserOut)
def valider_compte(user_id: int, taches: BackgroundTasks, db: Session = Depends(get_db),
                   admin: User = Depends(admin_requis)):
    """Autorise le compte : la personne peut maintenant se connecter (elle reçoit un email)."""
    return _decider(db, admin, user_id, "valide", taches)


@router.patch("/users/{user_id}/refuser", response_model=UserOut)
def refuser_compte(user_id: int, taches: BackgroundTasks, db: Session = Depends(get_db),
                   admin: User = Depends(admin_requis)):
    """Refuse le compte : la connexion est bloquée (un token déjà donné ne marche plus)."""
    return _decider(db, admin, user_id, "refuse", taches)


def _compter_par(db: Session, colonne, *conditions) -> dict[str, int]:
    """{valeur: nombre} pour une colonne, ex. {'olivier': 3, 'tomate': 1}."""
    requete = select(colonne, func.count()).where(*conditions).group_by(colonne)
    return {str(v): n for v, n in db.execute(requete).all() if v is not None}


def _pourcentage(part: int, total: int) -> float | None:
    return round(100 * part / total, 1) if total else None


@router.get("/stats", response_model=StatsAdmin)
def statistiques(db: Session = Depends(get_db), admin: User = Depends(admin_requis)):
    """Tableau de bord : comptes, parcelles, questions, qualité des photos, satisfaction."""
    nb_questions = db.scalar(select(func.count()).select_from(Message).where(Message.role == "user"))
    nb_reponses = db.scalar(select(func.count()).select_from(Message).where(Message.role == "assistant"))
    nb_photos = db.scalar(select(func.count()).select_from(Photo))
    nb_mauvaises = db.scalar(select(func.count()).select_from(Photo).where(Photo.qualite_ok.is_(False)))
    nb_avis = db.scalar(select(func.count()).select_from(Feedback))
    nb_utiles = db.scalar(select(func.count()).select_from(Feedback).where(Feedback.utile.is_(True)))
    return StatsAdmin(
        comptes=StatsComptes(
            total=db.scalar(select(func.count()).select_from(User)),
            par_statut=_compter_par(db, User.statut),
            par_role=_compter_par(db, User.role),
        ),
        parcelles=StatsParcelles(
            total=db.scalar(select(func.count()).select_from(Parcelle)),
            par_culture=_compter_par(db, Parcelle.culture),
        ),
        conversations=db.scalar(select(func.count()).select_from(Conversation)),
        questions=StatsQuestions(
            total=nb_questions,
            par_langue=_compter_par(db, Message.langue, Message.role == "user"),
            reponses_assistant=nb_reponses,
        ),
        photos=StatsPhotos(total=nb_photos, a_reprendre=nb_mauvaises,
                           taux_qualite_ok=_pourcentage(nb_photos - nb_mauvaises, nb_photos)),
        satisfaction=StatsSatisfaction(nb_avis=nb_avis, taux_utile=_pourcentage(nb_utiles, nb_avis)),
    )

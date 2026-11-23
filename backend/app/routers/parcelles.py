from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Parcelle, User
from ..schemas import ConversationDetail, Culture, ParcelleIn, ParcelleOut, ParcelleUpdate
from ..security import get_current_user

router = APIRouter(prefix="/parcelles", tags=["Parcelles"])


def get_parcelle_autorisee(parcelle_id: int, user: User, db: Session) -> Parcelle:
    """Renvoie la parcelle si elle appartient à l'utilisateur (ou si c'est un admin)."""
    parcelle = db.get(Parcelle, parcelle_id)
    if not parcelle or (parcelle.user_id != user.id and user.role != "admin"):
        # 404 dans les deux cas : on ne révèle pas l'existence des parcelles des autres
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcelle introuvable")
    return parcelle


@router.post("", response_model=ParcelleOut, status_code=status.HTTP_201_CREATED)
def creer_parcelle(data: ParcelleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    parcelle = Parcelle(user_id=user.id, **data.model_dump())
    db.add(parcelle)
    db.commit()
    db.refresh(parcelle)
    return parcelle


@router.get("", response_model=list[ParcelleOut])
def lister_parcelles(
    culture: Culture | None = Query(default=None, description="Filtrer par culture"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Parcelle).where(Parcelle.user_id == user.id).order_by(Parcelle.created_at.desc(), Parcelle.id.desc())
    if culture:
        query = query.where(Parcelle.culture == culture)
    return db.scalars(query).all()


@router.get("/{parcelle_id}", response_model=ParcelleOut)
def lire_parcelle(parcelle_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_parcelle_autorisee(parcelle_id, user, db)


@router.patch("/{parcelle_id}", response_model=ParcelleOut)
def modifier_parcelle(
    parcelle_id: int,
    data: ParcelleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parcelle = get_parcelle_autorisee(parcelle_id, user, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is None and field in ("nom", "culture"):
            continue  # champs obligatoires : on ignore un null envoyé par erreur
        setattr(parcelle, field, value)
    db.commit()
    db.refresh(parcelle)
    return parcelle


@router.delete("/{parcelle_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_parcelle(parcelle_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    parcelle = get_parcelle_autorisee(parcelle_id, user, db)
    db.delete(parcelle)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{parcelle_id}/historique",
    response_model=list[ConversationDetail],
    summary="Historique de la parcelle (questions, photos, réponses)",
)
def historique_parcelle(parcelle_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from .conversations import conversation_detail  # import local : évite un import circulaire

    parcelle = get_parcelle_autorisee(parcelle_id, user, db)
    convs = db.scalars(
        select(Conversation)
        .where(Conversation.parcelle_id == parcelle.id)
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
    ).all()
    return [conversation_detail(c) for c in convs]

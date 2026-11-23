from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Message, Photo, User
from ..schemas import (
    ConversationDetail,
    ConversationIn,
    ConversationOut,
    MessageOut,
    PhotoOut,
    ProblemePhoto,
    QuestionOut,
)
from ..security import get_current_user
from ..services.langue import detecter_langue
from ..services.photos import (
    MAX_PHOTOS,
    PhotoInvalide,
    enregistrer_photo,
    ouvrir_image,
    supprimer_fichier,
    verifier_qualite,
)
from .parcelles import get_parcelle_autorisee

router = APIRouter(prefix="/conversations", tags=["Conversations"])


# ---------- conversions modèle -> réponse ----------
def photo_out(photo: Photo) -> PhotoOut:
    return PhotoOut(id=photo.id, url=f"/uploads/{photo.chemin}", qualite_ok=photo.qualite_ok)


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        contenu=message.contenu,
        langue=message.langue,
        diagnostic=message.diagnostic,
        confiance=message.confiance,
        created_at=message.created_at,
        photos=[photo_out(p) for p in message.photos],
    )


def conversation_out(conv: Conversation) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        parcelle_id=conv.parcelle_id,
        titre=conv.titre,
        created_at=conv.created_at,
        nb_messages=len(conv.messages),
    )


def conversation_detail(conv: Conversation) -> ConversationDetail:
    return ConversationDetail(
        **conversation_out(conv).model_dump(),
        messages=[message_out(m) for m in conv.messages],
    )


def get_conversation_autorisee(conversation_id: int, user: User, db: Session) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if not conv or (conv.user_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation introuvable")
    return conv


# ---------- routes ----------
@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def creer_conversation(data: ConversationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.parcelle_id is not None:
        get_parcelle_autorisee(data.parcelle_id, user, db)  # 404 si ce n'est pas sa parcelle
    conv = Conversation(user_id=user.id, parcelle_id=data.parcelle_id, titre=data.titre)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conversation_out(conv)


@router.get("", response_model=list[ConversationOut])
def lister_conversations(
    parcelle_id: int | None = Query(default=None, description="Filtrer par parcelle"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Conversation).where(Conversation.user_id == user.id)
    if parcelle_id is not None:
        query = query.where(Conversation.parcelle_id == parcelle_id)
    query = query.order_by(Conversation.created_at.desc(), Conversation.id.desc())
    return [conversation_out(c) for c in db.scalars(query).all()]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def lire_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return conversation_detail(get_conversation_autorisee(conversation_id, user, db))


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_conversation(
    conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    conv = get_conversation_autorisee(conversation_id, user, db)
    chemins = [p.chemin for m in conv.messages for p in m.photos]
    db.delete(conv)
    db.commit()
    for chemin in chemins:  # supprime aussi les fichiers photo du disque
        supprimer_fichier(chemin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{conversation_id}/messages",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Poser une question (texte + jusqu'à 3 photos)",
)
async def poser_question(
    conversation_id: int,
    question: str = Form(min_length=1, max_length=2000, description="Question de l'agriculteur (fr ou ar)"),
    photos: list[UploadFile] = File(default=[], description="0 à 3 photos (JPEG, PNG, WEBP)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = get_conversation_autorisee(conversation_id, user, db)

    photos = [p for p in photos if p.filename]  # Swagger envoie parfois un champ fichier vide
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{MAX_PHOTOS} photos maximum par question")

    # 1) Vérifier toutes les photos AVANT d'enregistrer quoi que ce soit
    images = []
    for upload in photos:
        try:
            image = ouvrir_image(await upload.read())
        except PhotoInvalide as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{upload.filename} : {e}")
        images.append((upload.filename, image, verifier_qualite(image)))

    # 2) Enregistrer le message puis les photos
    message = Message(
        conversation_id=conv.id,
        role="user",
        contenu=question.strip(),
        langue=detecter_langue(question),
    )
    db.add(message)
    db.flush()  # pour obtenir message.id

    a_reprendre = []
    chemins = []
    try:
        for filename, image, qualite in images:
            chemin = enregistrer_photo(image)
            chemins.append(chemin)
            db.add(Photo(message_id=message.id, chemin=chemin, qualite_ok=qualite.ok))
            if not qualite.ok:
                a_reprendre.append(ProblemePhoto(fichier=filename, probleme=qualite.probleme))

        if not conv.titre:  # titre automatique = début de la première question
            conv.titre = question.strip()[:80]
        db.commit()
    except Exception:
        db.rollback()
        for chemin in chemins:
            supprimer_fichier(chemin)
        raise

    db.refresh(message)
    # La réponse de l'assistant (agent IA : VLM + RAG + météo) sera ajoutée dans une prochaine étape.
    return QuestionOut(message=message_out(message), photos_a_reprendre=a_reprendre)

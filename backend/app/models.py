from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# Statuts possibles d'un compte
STATUTS_COMPTE = ("en_attente", "valide", "refuse")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(150), unique=True)
    telephone: Mapped[str | None] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(Enum("agriculteur", "expert", "admin"), default="agriculteur")
    langue: Mapped[str] = mapped_column(Enum("fr", "ar"), default="fr")
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    # Un compte créé par /auth/register attend la validation d'un administrateur
    statut: Mapped[str] = mapped_column(Enum(*STATUTS_COMPTE), default="en_attente")
    valide_par: Mapped[int | None] = mapped_column(Integer)      # id de l'admin qui a décidé
    valide_le: Mapped[datetime | None] = mapped_column(DateTime)  # date de la décision
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


CULTURES = ("olivier", "tomate", "ble", "agrumes", "palmier_dattier", "autre")


class Parcelle(Base):
    __tablename__ = "parcelles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    nom: Mapped[str] = mapped_column(String(100))
    culture: Mapped[str] = mapped_column(Enum(*CULTURES))
    surface_ha: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    date_plantation: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    parcelle_id: Mapped[int | None] = mapped_column(ForeignKey("parcelles.id", ondelete="SET NULL"))
    titre: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.id", cascade="all, delete-orphan", passive_deletes=True
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(Enum("user", "assistant"))
    contenu: Mapped[str] = mapped_column(Text)
    langue: Mapped[str | None] = mapped_column(Enum("fr", "ar"))
    diagnostic: Mapped[str | None] = mapped_column(String(200))
    confiance: Mapped[float | None] = mapped_column(Float)
    temps_reponse_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    photos: Mapped[list["Photo"]] = relationship(
        back_populates="message", order_by="Photo.id", cascade="all, delete-orphan", passive_deletes=True
    )


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    chemin: Mapped[str] = mapped_column(String(255))
    qualite_ok: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    message: Mapped[Message] = relationship(back_populates="photos")
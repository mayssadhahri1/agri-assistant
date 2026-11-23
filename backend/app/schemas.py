from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterIn(BaseModel):
    nom: str = Field(min_length=2, max_length=100)
    email: EmailStr | None = None
    telephone: str | None = Field(default=None, pattern=r"^\+?\d{8,15}$")
    password: str = Field(min_length=6)
    langue: Literal["fr", "ar"] = "fr"

    @model_validator(mode="after")
    def email_ou_telephone(self):
        if not self.email and not self.telephone:
            raise ValueError("Email ou téléphone obligatoire")
        return self


class LoginIn(BaseModel):
    identifiant: str = Field(description="Email ou numéro de téléphone")
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    email: str | None
    telephone: str | None
    role: str
    langue: str
    actif: bool
    created_at: datetime


class UserUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=2, max_length=100)
    langue: Literal["fr", "ar"] | None = None


# ---------- Parcelles (F5) ----------
Culture = Literal["olivier", "tomate", "ble", "agrumes", "palmier_dattier", "autre"]


class ParcelleIn(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    culture: Culture
    surface_ha: float | None = Field(default=None, gt=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    date_plantation: date | None = None


class ParcelleUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    culture: Culture | None = None
    surface_ha: float | None = Field(default=None, gt=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    date_plantation: date | None = None


class ParcelleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    nom: str
    culture: str
    surface_ha: float | None
    latitude: float | None
    longitude: float | None
    date_plantation: date | None
    created_at: datetime


# ---------- Conversations / messages / photos (F1, F5) ----------
class ConversationIn(BaseModel):
    parcelle_id: int | None = Field(default=None, description="Parcelle concernée (recommandé)")
    titre: str | None = Field(default=None, max_length=200)


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    qualite_ok: bool | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    contenu: str
    langue: str | None
    diagnostic: str | None
    confiance: float | None
    created_at: datetime
    photos: list[PhotoOut] = []


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parcelle_id: int | None
    titre: str | None
    created_at: datetime
    nb_messages: int = 0


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class ProblemePhoto(BaseModel):
    fichier: str
    probleme: str


class QuestionOut(BaseModel):
    message: MessageOut
    photos_a_reprendre: list[ProblemePhoto] = Field(
        default=[], description="Photos floues ou trop sombres : demander à l'agriculteur de les reprendre"
    )

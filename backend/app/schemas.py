import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Role = Literal["agriculteur", "expert", "admin"]
Langue = Literal["fr", "ar"]
StatutCompte = Literal["en_attente", "valide", "refuse"]

# Rôles qu'on peut choisir dans le formulaire d'inscription.
# "admin" n'est jamais autorisé ici (à créer à la main en base).
# Retirez "expert" si vous voulez qu'un admin valide les experts.
ROLES_INSCRIPTION = ("agriculteur", "expert")


def normaliser_telephone(v: str) -> str:
    """'+216 20-123.456' -> '+21620123456'"""
    return re.sub(r"[\s\-.()]", "", v)


class UserCreate(BaseModel):
    nom: str = Field(min_length=2, max_length=100)
    email: EmailStr | None = None
    telephone: str | None = Field(default=None, max_length=25)
    password: str = Field(min_length=8)
    role: Role = "agriculteur"
    langue: Langue = "fr"

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v):
        if isinstance(v, str):
            v = v.strip().lower()
            return v or None          # "" envoyé par un formulaire -> None
        return v

    @field_validator("telephone", mode="before")
    @classmethod
    def clean_phone(cls, v):
        if isinstance(v, str):
            v = normaliser_telephone(v.strip())
            if not v:
                return None
            if not re.fullmatch(r"\+?\d{8,15}", v):
                raise ValueError("Numéro de téléphone invalide")
        return v

    @field_validator("nom")
    @classmethod
    def clean_nom(cls, v: str):
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_rules(cls, v: str):
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Mot de passe trop long (72 octets maximum)")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Le mot de passe doit contenir au moins une lettre et un chiffre")
        return v

    @model_validator(mode="after")
    def check_contact_and_role(self):
        if not self.email and not self.telephone:
            raise ValueError("Renseignez au moins un email ou un téléphone")
        if self.role not in ROLES_INSCRIPTION:
            raise ValueError("Ce rôle n'est pas disponible à l'inscription")
        return self


class LoginJSON(BaseModel):
    identifiant: str      # email OU téléphone
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    email: str | None
    telephone: str | None
    role: Role
    langue: Langue
    actif: bool
    statut: StatutCompte
    valide_le: datetime | None = None
    created_at: datetime


class InscriptionOut(UserOut):
    """Réponse de /auth/register : le compte est créé mais doit être validé."""

    message: str = "Compte créé. Il doit être validé par un administrateur avant de pouvoir se connecter."


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# =====================================================================
#  Conversations / messages / photos  (utilisés par routers/conversations.py)
# =====================================================================
class PhotoOut(BaseModel):
    id: int
    url: str
    qualite_ok: bool | None = None


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: Literal["user", "assistant"]
    contenu: str
    langue: Langue | None = None
    diagnostic: str | None = None
    confiance: float | None = None
    created_at: datetime
    photos: list[PhotoOut] = []


class ProblemePhoto(BaseModel):
    fichier: str
    probleme: str | None = None


class ConversationIn(BaseModel):
    parcelle_id: int | None = None
    titre: str | None = Field(default=None, max_length=200)


class ConversationOut(BaseModel):
    id: int
    parcelle_id: int | None = None
    titre: str | None = None
    created_at: datetime
    nb_messages: int = 0


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class QuestionOut(BaseModel):
    message: MessageOut
    photos_a_reprendre: list[ProblemePhoto] = []


# =====================================================================
#  Parcelles  (utilisés par routers/parcelles.py)
# =====================================================================
Culture = Literal["olivier", "tomate", "ble", "agrumes", "palmier_dattier", "autre"]


class ParcelleIn(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    culture: Culture
    surface_ha: float | None = Field(default=None, gt=0, le=99999999)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    date_plantation: date | None = None

    @field_validator("nom")
    @classmethod
    def clean_nom(cls, v: str):
        v = v.strip()
        if not v:
            raise ValueError("Le nom est obligatoire")
        return v


class ParcelleUpdate(BaseModel):
    """PATCH : tous les champs sont facultatifs, seuls ceux envoyés sont modifiés."""

    nom: str | None = Field(default=None, min_length=1, max_length=100)
    culture: Culture | None = None
    surface_ha: float | None = Field(default=None, gt=0, le=99999999)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    date_plantation: date | None = None

    @field_validator("nom")
    @classmethod
    def clean_nom(cls, v: str | None):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Le nom ne peut pas être vide")
        return v


class ParcelleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    nom: str
    culture: Culture
    surface_ha: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    date_plantation: date | None = None
    created_at: datetime
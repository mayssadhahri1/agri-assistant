"""Enregistrement des photos et contrôle de qualité (cahier des charges F1).

On vérifie qu'une photo n'est ni floue, ni trop sombre, ni surexposée,
pour pouvoir demander à l'agriculteur de la reprendre.
"""
import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
PHOTOS_DIR = UPLOAD_DIR / "photos"

MAX_PHOTOS = 3
MAX_TAILLE_OCTETS = 10 * 1024 * 1024  # 10 Mo
FORMATS_ACCEPTES = {"JPEG", "PNG", "WEBP"}

SEUIL_FLOU = 15.0       # variance du Laplacien : en dessous => photo floue (à ajuster sur de vraies photos)
SEUIL_SOMBRE = 40.0     # luminosité moyenne (0-255) : en dessous => trop sombre
SEUIL_SUREXPOSE = 225.0 # au-dessus => trop claire

# Noyau Laplacien : met en évidence les contours. Une photo nette a beaucoup de contours.
_LAPLACIEN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)


class PhotoInvalide(ValueError):
    pass


@dataclass
class ResultatQualite:
    ok: bool
    probleme: str | None
    nettete: float
    luminosite: float


def ouvrir_image(contenu: bytes) -> Image.Image:
    if len(contenu) > MAX_TAILLE_OCTETS:
        raise PhotoInvalide("Photo trop lourde (10 Mo maximum)")
    try:
        image = Image.open(io.BytesIO(contenu))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise PhotoInvalide("Le fichier n'est pas une image valide")
    if image.format not in FORMATS_ACCEPTES:
        raise PhotoInvalide("Format non accepté (JPEG, PNG ou WEBP)")
    # Applique la rotation EXIF des téléphones
    return ImageOps.exif_transpose(image).convert("RGB")


def verifier_qualite(image: Image.Image) -> ResultatQualite:
    gris = image.convert("L")
    gris.thumbnail((512, 512))  # taille fixe => seuils comparables entre photos
    luminosite = ImageStat.Stat(gris).mean[0]
    nettete = ImageStat.Stat(gris.filter(_LAPLACIEN)).var[0]

    probleme = None
    if luminosite < SEUIL_SOMBRE:
        probleme = "Photo trop sombre : reprenez-la avec plus de lumière"
    elif luminosite > SEUIL_SUREXPOSE:
        probleme = "Photo trop claire : évitez le soleil direct sur l'objectif"
    elif nettete < SEUIL_FLOU:
        probleme = "Photo floue : tenez le téléphone immobile et faites la mise au point"
    return ResultatQualite(probleme is None, probleme, round(nettete, 1), round(luminosite, 1))


def enregistrer_photo(image: Image.Image) -> str:
    """Enregistre en JPEG et renvoie le chemin relatif (ex : photos/abc.jpg)."""
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    nom = f"{uuid.uuid4().hex}.jpg"
    image.save(PHOTOS_DIR / nom, "JPEG", quality=90)
    return f"photos/{nom}"


def supprimer_fichier(chemin: str) -> None:
    (UPLOAD_DIR / chemin).unlink(missing_ok=True)

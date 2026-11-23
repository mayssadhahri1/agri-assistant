"""Détection simple de la langue de la question (cahier des charges F4)."""
import re

_ARABE = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿ]")
_LETTRE = re.compile(r"[^\W\d_]")


def detecter_langue(texte: str) -> str:
    """Renvoie 'ar' si la majorité des lettres sont arabes, sinon 'fr'.

    Le dialecte tunisien écrit en lettres latines (« 3andi mochkla ») est
    traité comme 'fr' pour l'instant ; le modèle de langue gérera ce cas plus tard.
    """
    lettres = _LETTRE.findall(texte)
    if not lettres:
        return "fr"
    nb_arabe = sum(1 for c in lettres if _ARABE.match(c))
    return "ar" if nb_arabe / len(lettres) >= 0.5 else "fr"

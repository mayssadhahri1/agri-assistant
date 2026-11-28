"""Pages ouvertes depuis l'email de l'admin (boutons Accepter / Refuser)
et boîte mail de test (/dev/emails) quand SMTP n'est pas configuré.

Le clic sur le bouton ouvre une page de confirmation (GET), et c'est le bouton
« Confirmer » de cette page (POST) qui applique la décision. Ainsi, un antivirus
ou une messagerie qui « visite » les liens ne peut pas valider un compte tout seul.
"""
import html
import re

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services.emails import EMAILS_DEV_DIR, lire_token_decision, mode_test, notifier_client_decision
from .admin import appliquer_decision

router = APIRouter(tags=["Validation par email"])

ACTIONS = {
    "valider": {"statut": "valide", "verbe": "Accepter", "couleur": "#2f8f3a"},
    "refuser": {"statut": "refuse", "verbe": "Refuser", "couleur": "#c0392b"},
}
LIBELLES_STATUT = {"en_attente": "en attente", "valide": "validé", "refuse": "refusé"}


def _page(titre: str, contenu: str, code: int = 200) -> HTMLResponse:
    """Page HTML simple, avec le même style que les emails."""
    return HTMLResponse(status_code=code, content=f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titre)}</title></head>
<body style="margin:0;background:#f3f5f0;font-family:Segoe UI,Arial,sans-serif;color:#1f2a1c">
<div style="max-width:560px;margin:48px auto;background:#fff;border:1px solid #dfe6d8;border-radius:12px;overflow:hidden">
  <div style="background:#2f6b2f;color:#fff;padding:18px 28px;font-size:18px;font-weight:600">🌿 Assistant agricole · Administration</div>
  <div style="padding:28px"><h1 style="margin:0 0 16px;font-size:20px">{html.escape(titre)}</h1>{contenu}</div>
</div></body></html>""")


def _fiche(user: User) -> str:
    td = "padding:6px 10px;border-bottom:1px solid #eef2ea"
    lignes = [("Nom", user.nom), ("Email", user.email or "—"), ("Téléphone", user.telephone or "—"),
              ("Rôle", user.role), ("Statut actuel", LIBELLES_STATUT.get(user.statut, user.statut))]
    corps = "".join(f'<tr><td style="{td};color:#6b7768;width:130px">{k}</td>'
                    f'<td style="{td}"><b>{html.escape(str(v))}</b></td></tr>' for k, v in lignes)
    return f'<table style="width:100%;border-collapse:collapse;margin:0 0 22px;font-size:14px">{corps}</table>'


def _verifier(token: str, db: Session) -> tuple[dict, User, User]:
    """Vérifie le lien reçu par email : signature, date, admin toujours admin, compte existant."""
    try:
        data = lire_token_decision(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(410, "Ce lien a expiré. Décidez depuis Swagger (section Administration).")
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(400, "Lien invalide.")
    admin = db.get(User, data.get("admin"))
    if admin is None or admin.role != "admin" or admin.statut != "valide" or not admin.actif:
        raise HTTPException(403, "Ce lien n'est plus valable : son administrateur n'a plus les droits.")
    user = db.get(User, int(data["sub"]))
    if user is None:
        raise HTTPException(404, "Ce compte n'existe plus.")
    return data, admin, user


def _erreur(e: HTTPException) -> HTMLResponse:
    return _page("Action impossible", f'<p style="color:#c0392b">{html.escape(str(e.detail))}</p>', e.status_code)


@router.get("/comptes/decision", response_class=HTMLResponse)
def page_decision(token: str = Query(...), db: Session = Depends(get_db)):
    """Page ouverte par le bouton de l'email : montre le compte et demande de confirmer."""
    try:
        data, admin, user = _verifier(token, db)
    except HTTPException as e:
        return _erreur(e)
    act = ACTIONS[data["action"]]
    if user.statut != "en_attente":
        return _page("Demande déjà traitée",
                     _fiche(user) + "<p>Ce compte a déjà été traité. Rien n'a été changé.</p>")
    formulaire = (
        '<form method="post" action="/comptes/decision">'
        f'<input type="hidden" name="token" value="{html.escape(token)}">'
        f'<button type="submit" style="padding:12px 26px;border:0;border-radius:8px;background:{act["couleur"]};'
        f'color:#fff;font-weight:600;font-size:15px;cursor:pointer">Confirmer : {act["verbe"].lower()} ce compte</button>'
        "</form>"
    )
    return _page(f"{act['verbe']} l'inscription ?",
                 f"<p>Bonjour {html.escape(admin.nom)}, vous allez <b>{act['verbe'].lower()}</b> ce compte :</p>"
                 + _fiche(user) + formulaire)


@router.post("/comptes/decision", response_class=HTMLResponse)
def appliquer_depuis_email(taches: BackgroundTasks, token: str = Form(...), db: Session = Depends(get_db)):
    """Applique la décision (bouton « Confirmer » de la page) et prévient la personne par email."""
    try:
        data, admin, user = _verifier(token, db)
        if user.statut != "en_attente":
            return _page("Demande déjà traitée", _fiche(user) + "<p>Rien n'a été changé.</p>")
        act = ACTIONS[data["action"]]
        user = appliquer_decision(db, admin, user, act["statut"])
    except HTTPException as e:
        return _erreur(e)
    taches.add_task(notifier_client_decision, user.id)
    message = ("La personne peut maintenant se connecter." if user.statut == "valide"
               else "La personne ne pourra pas se connecter.")
    return _page("Compte validé ✅" if user.statut == "valide" else "Compte refusé",
                 _fiche(user) + f"<p>{message} Elle a été prévenue par email.</p>")


# ---------------------------------------------------------------- boîte de test
def _exiger_mode_test():
    # En production (SMTP configuré) la boîte de test n'existe pas
    if not mode_test():
        raise HTTPException(404, "Not Found")


@router.get("/dev/emails", response_class=HTMLResponse, dependencies=[Depends(_exiger_mode_test)])
def boite_de_test():
    """Mode test (SMTP vide) : liste des emails « envoyés », le plus récent en haut."""
    fichiers = sorted(EMAILS_DEV_DIR.glob("*.html"), reverse=True) if EMAILS_DEV_DIR.exists() else []
    lignes = []
    for f in fichiers[:50]:
        tete = f.read_text(encoding="utf-8")[:400]
        a = re.search(r"<!-- to: (.*?) -->", tete)
        s = re.search(r"<!-- subject: (.*?) -->", tete)
        lignes.append(
            f'<tr><td style="padding:8px;border-bottom:1px solid #eef2ea">{a.group(1) if a else ""}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #eef2ea"><a href="/dev/emails/{html.escape(f.name)}">'
            f'{s.group(1) if s else f.name}</a></td></tr>')
    contenu = ("<p>Aucun serveur SMTP n'est configuré : les emails sont gardés ici.</p>"
               '<table style="width:100%;border-collapse:collapse;font-size:14px">'
               '<tr><th align="left" style="padding:8px">Destinataire</th><th align="left" style="padding:8px">Sujet</th></tr>'
               + ("".join(lignes) or '<tr><td colspan="2" style="padding:8px">Aucun email.</td></tr>') + "</table>")
    return _page("Boîte mail de test", contenu)


@router.get("/dev/emails/{nom}", response_class=HTMLResponse, dependencies=[Depends(_exiger_mode_test)])
def lire_email_test(nom: str):
    """Affiche un email de la boîte de test."""
    if not re.fullmatch(r"[\w\-.]+\.html", nom):
        raise HTTPException(400, "Nom invalide")
    f = EMAILS_DEV_DIR / nom
    if not f.is_file():
        raise HTTPException(404, "Email introuvable")
    return HTMLResponse(f.read_text(encoding="utf-8"))

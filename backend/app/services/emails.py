"""Envoi des emails liés à la validation des comptes.

- Avec SMTP configuré (.env) : l'email part vraiment (Gmail, Outlook, ...).
- Sans SMTP (mode test) : l'email est enregistré en .html dans backend/emails_dev/
  et on peut l'ouvrir sur http://127.0.0.1:<port>/dev/emails
"""
import html
import logging
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import jwt
from sqlalchemy import select

from ..config import settings
from ..database import SessionLocal
from ..models import User

log = logging.getLogger("emails")

# Dossier de la boîte mail de test
EMAILS_DEV_DIR = Path(__file__).resolve().parent.parent.parent / "emails_dev"

DECISION_TYPE = "decision_compte"


def mode_test() -> bool:
    """Vrai si aucun serveur SMTP n'est configuré."""
    return not settings.smtp_host


# ---------------------------------------------------------------- liens signés
def creer_token_decision(user_id: int, admin_id: int, action: str) -> str:
    """Token signé mis dans les boutons de l'email (valable quelques jours)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.decision_lien_heures)
    payload = {"type": DECISION_TYPE, "sub": str(user_id), "admin": admin_id, "action": action, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def lire_token_decision(token: str) -> dict:
    """Renvoie le contenu du token, ou lève jwt.PyJWTError / ValueError."""
    data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if data.get("type") != DECISION_TYPE or data.get("action") not in ("valider", "refuser"):
        raise ValueError("Token invalide")
    return data


# ---------------------------------------------------------------- envoi
def envoyer_email(destinataire: str, sujet: str, corps_html: str) -> None:
    """Envoie l'email (SMTP) ou l'enregistre dans la boîte de test."""
    if mode_test():
        EMAILS_DEV_DIR.mkdir(exist_ok=True)
        horodatage = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        nom = re.sub(r"[^a-zA-Z0-9]+", "_", f"{destinataire}_{sujet}")[:80]
        fichier = EMAILS_DEV_DIR / f"{horodatage}_{nom}.html"
        entete = (
            f"<!-- to: {html.escape(destinataire)} -->\n<!-- subject: {html.escape(sujet)} -->\n"
        )
        fichier.write_text(entete + corps_html, encoding="utf-8")
        log.info("Email (mode test) enregistré : %s", fichier.name)
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = destinataire
    msg["Subject"] = sujet
    msg.set_content("Ouvrez cet email dans une application qui affiche le HTML.")
    msg.add_alternative(corps_html, subtype="html")
    try:
        # Port 465 = connexion SSL directe ; sinon (587) on passe en TLS avec STARTTLS
        if settings.smtp_port == 465:
            serveur = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20)
        else:
            serveur = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        with serveur as smtp:
            if settings.smtp_port != 465:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        log.info("Email envoyé à %s : %s", destinataire, sujet)
    except Exception:
        # Un email qui ne part pas ne doit pas faire échouer l'inscription
        log.exception("Envoi de l'email à %s impossible", destinataire)


# ---------------------------------------------------------------- mise en page
def _gabarit(titre: str, contenu: str) -> str:
    """Mise en page commune de tous les emails."""
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>{html.escape(titre)}</title></head>
<body style="margin:0;background:#f3f5f0;font-family:Segoe UI,Arial,sans-serif;color:#1f2a1c">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #dfe6d8">
        <tr><td style="background:#2f6b2f;color:#ffffff;padding:18px 28px;font-size:18px;font-weight:600">
          🌿 Assistant agricole
        </td></tr>
        <tr><td style="padding:28px">
          <h1 style="margin:0 0 16px;font-size:20px">{html.escape(titre)}</h1>
          {contenu}
        </td></tr>
        <tr><td style="padding:14px 28px;background:#f8faf6;color:#6b7768;font-size:12px">
          Email automatique, merci de ne pas y répondre.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _bouton(texte: str, url: str, couleur: str) -> str:
    return (
        f'<a href="{html.escape(url)}" style="display:inline-block;padding:12px 26px;margin:0 8px 8px 0;'
        f'background:{couleur};color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600">'
        f"{html.escape(texte)}</a>"
    )


def _fiche(user: User) -> str:
    """Petit tableau avec les informations du compte."""
    lignes = [
        ("Nom", user.nom),
        ("Email", user.email or "—"),
        ("Téléphone", user.telephone or "—"),
        ("Rôle", user.role),
        ("Langue", user.langue),
        ("Inscrit le", user.created_at.strftime("%d/%m/%Y %H:%M") if user.created_at else "—"),
    ]
    td = "padding:6px 10px;border-bottom:1px solid #eef2ea"
    corps = "".join(
        f'<tr><td style="{td};color:#6b7768;width:120px">{k}</td><td style="{td}"><b>{html.escape(str(v))}</b></td></tr>'
        for k, v in lignes
    )
    return f'<table cellpadding="0" cellspacing="0" style="width:100%;margin:0 0 22px;font-size:14px">{corps}</table>'


# ---------------------------------------------------------------- emails métier
def notifier_admins_inscription(user_id: int, base_url: str) -> None:
    """Tâche de fond : un email à chaque admin avec les boutons Accepter / Refuser."""
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            return
        admins = db.scalars(
            select(User).where(User.role == "admin", User.statut == "valide",
                               User.actif.is_(True), User.email.is_not(None))
        ).all()
        for admin in admins:
            lien = f"{base_url.rstrip('/')}/comptes/decision?token="
            ok = lien + creer_token_decision(user.id, admin.id, "valider")
            ko = lien + creer_token_decision(user.id, admin.id, "refuser")
            contenu = (
                f"<p>Bonjour {html.escape(admin.nom)},</p>"
                "<p>Une nouvelle personne demande à utiliser l'application :</p>"
                + _fiche(user)
                + _bouton("✔ Accepter le compte", ok, "#2f8f3a")
                + _bouton("✖ Refuser", ko, "#c0392b")
                + f'<p style="color:#6b7768;font-size:12px;margin-top:18px">Les boutons sont valables '
                f"{settings.decision_lien_heures} heures. Vous pouvez aussi décider depuis Swagger "
                "(section Administration).</p>"
            )
            envoyer_email(admin.email, f"Nouvelle inscription à valider : {user.nom}",
                          _gabarit("Nouvelle inscription à valider", contenu))


def notifier_client_decision(user_id: int) -> None:
    """Tâche de fond : prévient la personne que son compte est validé ou refusé."""
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.email:
            return   # inscrit seulement par téléphone : pas d'email possible
        if user.statut == "valide":
            titre = "Votre compte est validé ✅"
            contenu = (
                f"<p>Bonjour {html.escape(user.nom)},</p>"
                "<p>Bonne nouvelle : un administrateur a <b>accepté</b> votre inscription.</p>"
                "<p>Vous pouvez maintenant vous connecter avec votre email ou votre téléphone "
                "et votre mot de passe.</p>"
            )
        elif user.statut == "refuse":
            titre = "Votre inscription n'a pas été acceptée"
            contenu = (
                f"<p>Bonjour {html.escape(user.nom)},</p>"
                "<p>Un administrateur a <b>refusé</b> votre demande d'inscription.</p>"
                "<p>Si vous pensez que c'est une erreur, contactez l'équipe de l'application.</p>"
            )
        else:
            return
        envoyer_email(user.email, titre, _gabarit(titre, contenu))


def envoyer_reinitialisation(user_id: int, base_url: str) -> None:
    """Tâche de fond : email avec le bouton « Choisir un nouveau mot de passe » (valable 1 h)."""
    from ..security import RESET_MINUTES, create_reset_token   # import ici : évite un import circulaire

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.email:
            return
        lien = f"{base_url.rstrip('/')}/comptes/mot-de-passe?token={create_reset_token(user)}"
        contenu = (
            f"<p>Bonjour {html.escape(user.nom)},</p>"
            "<p>Vous avez demandé à changer votre mot de passe.</p>"
            + _bouton("Choisir un nouveau mot de passe", lien, "#2f6b2f")
            + f'<p style="color:#6b7768;font-size:12px;margin-top:18px">Ce lien est valable {RESET_MINUTES} minutes '
            "et ne marche qu'une fois. Si vous n'avez rien demandé, ignorez cet email : "
            "votre mot de passe actuel reste valable.</p>"
        )
        envoyer_email(user.email, "Réinitialisation de votre mot de passe",
                      _gabarit("Mot de passe oublié", contenu))

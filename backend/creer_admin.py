"""Prépare la base pour la validation des comptes et crée un administrateur.

    python creer_admin.py                               # admin@agri.tn / Admin1234
    python creer_admin.py mon@email.com MonMotDePasse1

1. Ajoute les colonnes statut / valide_par / valide_le à la table users (si absentes).
   Les comptes qui existaient déjà sont marqués "valide" pour ne pas les bloquer.
2. Crée le compte administrateur (ou le remet admin + validé s'il existe déjà).
"""
import sys

from sqlalchemy import inspect, select, text

from app.database import SessionLocal, engine
from app.models import User
from app.security import hash_password

email = (sys.argv[1] if len(sys.argv) > 1 else "admin@agri.tn").strip().lower()
password = sys.argv[2] if len(sys.argv) > 2 else "Admin1234"

# --- 1. Migration : nouvelles colonnes dans users ---
colonnes = {c["name"] for c in inspect(engine).get_columns("users")}
with engine.begin() as conn:
    if "statut" not in colonnes:
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN statut ENUM('en_attente','valide','refuse') "
            "NOT NULL DEFAULT 'en_attente' AFTER actif"
        ))
        # Les anciens comptes restent utilisables
        conn.execute(text("UPDATE users SET statut = 'valide'"))
        print("Colonne statut ajoutée (comptes existants marqués 'valide').")
    if "valide_par" not in colonnes:
        conn.execute(text("ALTER TABLE users ADD COLUMN valide_par INT NULL AFTER statut"))
    if "valide_le" not in colonnes:
        conn.execute(text("ALTER TABLE users ADD COLUMN valide_le DATETIME NULL AFTER valide_par"))

# --- 2. Compte administrateur ---
with SessionLocal() as db:
    admin = db.scalar(select(User).where(User.email == email))
    if admin is None:
        admin = User(nom="Administrateur", email=email, password_hash=hash_password(password))
        db.add(admin)
        print(f"Administrateur créé : {email}")
    else:
        admin.password_hash = hash_password(password)
        print(f"Compte {email} mis à jour en administrateur")
    admin.role = "admin"
    admin.statut = "valide"
    admin.actif = True
    db.commit()

print(f"Connexion Swagger : username = {email} / password = {password}")

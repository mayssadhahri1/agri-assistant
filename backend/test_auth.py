"""Teste inscription / connexion sur l'API en cours d'exécution.

    python test_auth.py                      # http://127.0.0.1:8000
    python test_auth.py http://127.0.0.1:8001

Crée un utilisateur de test (email test<nombre>@example.com) à chaque exécution.
Il faut un compte admin (créé par : python creer_admin.py). Identifiants admin
lus dans ADMIN_EMAIL / ADMIN_PASSWORD (par défaut admin@agri.tn / Admin1234).
"""
import os
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@agri.tn")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin1234")


def call(method, path, body=None, token=None, form=False):
    headers = {}
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode(errors="replace")


results = []


def check(label, got, expected):
    ok = got == expected
    results.append(ok)
    print(f"[{'OK ' if ok else 'ECHEC'}] {label:<46} attendu {expected}, obtenu {got}")
    return ok


n = int(time.time() * 1000)
email = f"test{n}@example.com"
digits = str(n)[-8:]
tel_saisi = f"+216 {digits[:2]} {digits[2:5]} {digits[5:]}"
pwd = "motdepasse1"

print(f"Serveur : {BASE}\n")

try:
    s, _ = call("GET", "/health")
except Exception as e:
    print(f"Impossible de joindre le serveur : {e}\nLancez d'abord : python -m uvicorn app.main:app --reload")
    sys.exit(2)
check("Serveur démarré (GET /health)", s, 200)

# --- inscription ---
s, user = call("POST", "/auth/register", {"nom": "Ali Test", "email": email, "telephone": tel_saisi,
                                         "password": pwd, "role": "agriculteur", "langue": "fr"})
check("Inscription valide", s, 201)
if s == 201:
    check("  rôle enregistré", user.get("role"), "agriculteur")
    check("  mot de passe jamais renvoyé", "password" in user or "password_hash" in user, False)
else:
    print("  détail :", user)

s, _ = call("POST", "/auth/register", {"nom": "Doublon", "email": email, "password": pwd})
check("Inscription email déjà utilisé", s, 409)
s, _ = call("POST", "/auth/register", {"nom": "Doublon", "telephone": tel_saisi, "password": pwd})
check("Inscription téléphone déjà utilisé", s, 409)
s, _ = call("POST", "/auth/register", {"nom": "Sans contact", "password": pwd})
check("Inscription sans email ni téléphone", s, 422)
s, _ = call("POST", "/auth/register", {"nom": "Pirate", "email": f"a{email}", "password": pwd, "role": "admin"})
check("Inscription avec rôle admin refusée", s, 422)
s, _ = call("POST", "/auth/register", {"nom": "Faible", "email": f"b{email}", "password": "motdepasse"})
check("Inscription mot de passe sans chiffre", s, 422)

if s == 201:
    check("  statut en_attente", user.get("statut"), "en_attente")

# --- validation par l'administrateur ---
s, _ = call("POST", "/auth/login/json", {"identifiant": email, "password": pwd})
check("Login AVANT validation admin", s, 403)
s, adm = call("POST", "/auth/login/json", {"identifiant": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
check("Login administrateur", s, 200)
if s != 200:
    print("  -> lancez d'abord : python creer_admin.py")
    sys.exit(1)
tok_admin = adm["access_token"]
s, attente = call("GET", "/admin/users?statut=en_attente", token=tok_admin)
check("Admin : liste des comptes en attente", s, 200)
uid = user.get("id") if isinstance(user, dict) else None
check("  le nouveau compte est dans la liste", any(u["id"] == uid for u in attente or []), True)
s, valide = call("PATCH", f"/admin/users/{uid}/valider", token=tok_admin)
check("Admin : valider le compte", s, 200)
check("  statut valide", (valide or {}).get("statut"), "valide")

# --- connexion ---
s, tok = call("POST", "/auth/login/json", {"identifiant": email, "password": pwd})
check("Login JSON par email", s, 200)
token = tok.get("access_token") if isinstance(tok, dict) else None
check("  token reçu", bool(token), True)
s, _ = call("POST", "/auth/login/json", {"identifiant": tel_saisi, "password": pwd})
check("Login JSON par téléphone (avec espaces)", s, 200)
s, _ = call("POST", "/auth/login", {"username": email, "password": pwd}, form=True)
check("Login formulaire (Swagger)", s, 200)
s, _ = call("POST", "/auth/login/json", {"identifiant": email, "password": "faux12345"})
check("Login mauvais mot de passe", s, 401)
s, _ = call("POST", "/auth/login/json", {"identifiant": "inconnu@example.com", "password": pwd})
check("Login utilisateur inconnu", s, 401)

# --- route protégée ---
s, me = call("GET", "/auth/me", token=token)
check("GET /auth/me avec token", s, 200)
if s == 200:
    check("  email correct", me.get("email"), email)
s, _ = call("GET", "/auth/me")
check("GET /auth/me sans token", s, 401)
s, _ = call("GET", "/auth/me", token="abc.def.ghi")
check("GET /auth/me token invalide", s, 401)

# --- sécurité des routes admin ---
s, _ = call("GET", "/admin/users", token=token)
check("Agriculteur sur /admin/users", s, 403)
s, _ = call("GET", "/admin/users")
check("/admin/users sans token", s, 401)

# --- compte refusé ---
email_r = f"r{email}"
s, refuse = call("POST", "/auth/register", {"nom": "Refusé", "email": email_r, "password": pwd})
check("Inscription d'un 2e compte", s, 201)
s, _ = call("PATCH", f"/admin/users/{refuse.get('id')}/refuser", token=tok_admin)
check("Admin : refuser le compte", s, 200)
s, _ = call("POST", "/auth/login/json", {"identifiant": email_r, "password": pwd})
check("Login d'un compte refusé", s, 403)
s, _ = call("PATCH", "/admin/users/999999999/valider", token=tok_admin)
check("Valider un compte inexistant", s, 404)

print(f"\n{sum(results)}/{len(results)} tests réussis")
sys.exit(0 if all(results) else 1)
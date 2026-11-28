"""Tests de l'étape 5 : profil, mots de passe, statistiques admin, routes RAG protégées.

    python test_etape5.py                        # http://127.0.0.1:8000
    python test_etape5.py http://127.0.0.1:8001

Il faut un admin (python creer_admin.py) ; identifiants lus dans ADMIN_EMAIL / ADMIN_PASSWORD
(par défaut admin@agri.tn / Admin1234). Le test « mot de passe oublié » lit la boîte de test
/dev/emails : il ne marche que si SMTP n'est pas configuré.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ADMIN = (os.environ.get("ADMIN_EMAIL", "admin@agri.tn"), os.environ.get("ADMIN_PASSWORD", "Admin1234"))


def call(method, path, body=None, token=None, raw=False):
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            txt = r.read().decode()
            return r.status, (txt if raw else json.loads(txt or "null"))
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")
        try:
            return e.code, (txt if raw else json.loads(txt))
        except Exception:
            return e.code, txt


results = []


def check(label, got, expected):
    ok = got == expected
    results.append(ok)
    print(f"[{'OK ' if ok else 'ECHEC'}] {label:<52} attendu {expected}, obtenu {got}")


def login(ident, pwd):
    return call("POST", "/auth/login/json", {"identifiant": ident, "password": pwd})


print(f"Serveur : {BASE}\n")
try:
    call("GET", "/health")
except Exception as e:
    print(f"Impossible de joindre le serveur : {e}")
    sys.exit(2)

# --- préparation : un agriculteur validé par l'admin
s, adm = login(*ADMIN)
if s != 200:
    print("Login admin impossible : lancez d'abord python creer_admin.py")
    sys.exit(2)
t_admin = adm["access_token"]
n = int(time.time() * 1000)
email, pwd = f"profil{n}@example.com", "motdepasse1"
s, u = call("POST", "/auth/register", {"nom": "Test Profil", "email": email, "password": pwd})
call("PATCH", f"/admin/users/{u['id']}/valider", token=t_admin)
tok = login(email, pwd)[1]["access_token"]

print("--- Profil ---")
s, p = call("PATCH", "/auth/me", {"nom": "Nouveau Nom", "langue": "ar", "telephone": f"+216 5{str(n)[-7:]}"}, tok)
check("PATCH /auth/me (nom, langue, téléphone)", s, 200)
check("  nom modifié", p.get("nom"), "Nouveau Nom")
check("  langue modifiée", p.get("langue"), "ar")
check("PATCH /auth/me vide", call("PATCH", "/auth/me", {}, tok)[0], 422)
check("PATCH /auth/me téléphone invalide", call("PATCH", "/auth/me", {"telephone": "abc"}, tok)[0], 422)
check("PATCH /auth/me sans token", call("PATCH", "/auth/me", {"nom": "X Y"})[0], 401)

print("\n--- Changement de mot de passe ---")
mdp = "/auth/me/mot-de-passe"
check("Ancien mot de passe faux", call("POST", mdp, {"ancien_mot_de_passe": "faux12345", "nouveau_mot_de_passe": "nouveau123"}, tok)[0], 400)
check("Nouveau mot de passe trop faible", call("POST", mdp, {"ancien_mot_de_passe": pwd, "nouveau_mot_de_passe": "court"}, tok)[0], 422)
check("Changement correct", call("POST", mdp, {"ancien_mot_de_passe": pwd, "nouveau_mot_de_passe": "nouveau123"}, tok)[0], 200)
check("Login avec l'ancien mot de passe", login(email, pwd)[0], 401)
check("Login avec le nouveau mot de passe", login(email, "nouveau123")[0], 200)

print("\n--- Mot de passe oublié ---")
s, r = call("POST", "/auth/mot-de-passe-oublie", {"email": email})
check("Demande pour un compte existant", s, 202)
s2, r2 = call("POST", "/auth/mot-de-passe-oublie", {"email": f"inconnu{n}@example.com"})
check("Demande pour un email inconnu (même réponse)", (s2, r2), (s, r))
time.sleep(1)
s, boite = call("GET", "/dev/emails", raw=True)
if s != 200:
    print("  (boîte de test absente : SMTP configuré, tests de réinitialisation ignorés)")
else:
    lien = next(m for m in re.findall(r'href="(/dev/emails/[^"]+)"', boite) if "profil" in m and "initialisation" in m)
    contenu = call("GET", lien, raw=True)[1]
    token = re.search(r"token=([\w\-.]+)", contenu).group(1)
    check("Lien reçu par email : page ouverte", call("GET", f"/comptes/mot-de-passe?token={token}", raw=True)[0], 200)
    rp = "/auth/reinitialiser-mot-de-passe"
    check("Réinitialisation avec le lien", call("POST", rp, {"token": token, "nouveau_mot_de_passe": "oubli2026"})[0], 200)
    check("Même lien une 2e fois (usage unique)", call("POST", rp, {"token": token, "nouveau_mot_de_passe": "autre2026"})[0], 400)
    check("Lien falsifié", call("POST", rp, {"token": "abc.def.ghi", "nouveau_mot_de_passe": "autre2026"})[0], 400)
    check("Login avec le mot de passe réinitialisé", login(email, "oubli2026")[0], 200)

print("\n--- Statistiques admin ---")
s, st = call("GET", "/admin/stats", token=t_admin)
check("GET /admin/stats (admin)", s, 200)
check("  contient comptes, parcelles, questions, photos", all(k in st for k in ("comptes", "parcelles", "questions", "photos")), True)
tok = login(email, "oubli2026")[1].get("access_token") or tok
check("GET /admin/stats (agriculteur)", call("GET", "/admin/stats", token=tok)[0], 403)

print("\n--- Routes RAG protégées ---")
s, _ = call("GET", "/rag/stats")
if s == 404:
    print("  (RAG désactivé : chromadb non installé, tests ignorés)")
else:
    check("/rag/stats sans token", s, 401)
    check("/rag/index-all par un agriculteur", call("POST", "/rag/index-all", token=tok)[0], 403)
    check("/rag/search sans token", call("POST", "/rag/search", {"question": "olivier feuilles jaunes"})[0], 401)

print(f"\n{sum(results)}/{len(results)} tests réussis")
sys.exit(0 if all(results) else 1)

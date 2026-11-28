"""Test complet de l'API : santé, parcelles, conversations, photos, arabe, sécurité.

    python test_api.py                       # http://127.0.0.1:8000
    python test_api.py http://127.0.0.1:8001

Crée 2 utilisateurs de test (test<nombre>a@example.com / ...b@example.com) et
nettoie ce qu'il crée (parcelle, conversation, photos).
Nécessite Pillow (déjà dans requirements.txt) pour fabriquer les images de test.
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

try:
    from PIL import Image
except ImportError:
    print("Pillow est requis : python -m pip install pillow")
    sys.exit(2)

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"


# ---------------------------------------------------------------- outils
def call(method, path, body=None, token=None, multipart=None):
    headers, data = {}, None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if multipart is not None:
        data, headers["Content-Type"] = multipart
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode(errors="replace")


def get_raw(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, "", b""


def build_multipart(fields, files):
    boundary = "----agriTest" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8"))
    for name, filename, content, ctype in files:
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n").encode()
        parts.append(head + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def image_bytes(kind):
    """'net' = image nette et contrastée ; 'sombre' = quasi noire."""
    img = (Image.effect_noise((800, 600), 40).convert("RGB") if kind == "net"
           else Image.new("RGB", (800, 600), (4, 4, 4)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)
    return buf.getvalue()


results = []


def check(label, got, expected):
    ok = got == expected
    results.append(ok)
    print(f"[{'OK ' if ok else 'ECHEC'}] {label:<52} attendu {expected}, obtenu {got}")
    return ok


def info(label, value):
    print(f"[info] {label:<52} {value}")


def question(token, cid, texte, photos=()):
    files = [("photos", f"p{i}.jpg", content, ctype) for i, (content, ctype) in enumerate(photos)]
    return call("POST", f"/conversations/{cid}/messages", token=token,
                multipart=build_multipart({"question": texte}, files))


# ---------------------------------------------------------------- préparation
print(f"Serveur : {BASE}\n")
try:
    s, h = call("GET", "/health")
except Exception as e:
    print(f"Impossible de joindre le serveur : {e}\nLancez : python -m uvicorn app.main:app --reload")
    sys.exit(2)

print("--- Santé ---")
check("GET /health", s, 200)
check("  base de données connectée", (h or {}).get("database"), "connectée")

n = int(time.time() * 1000)
pwd = "motdepasse1"
mail_a, mail_b = f"test{n}a@example.com", f"test{n}b@example.com"
for m in (mail_a, mail_b):
    s, _ = call("POST", "/auth/register", {"nom": "Testeur", "email": m, "password": pwd})
    if s != 201:
        print("Inscription impossible, détail :", _)
        sys.exit(2)
# Les nouveaux comptes doivent être validés par l'admin (python creer_admin.py)
s, adm = call("POST", "/auth/login/json", {"identifiant": os.environ.get("ADMIN_EMAIL", "admin@agri.tn"),
                                          "password": os.environ.get("ADMIN_PASSWORD", "Admin1234")})
if s != 200:
    print("Login admin impossible, lancez d'abord : python creer_admin.py")
    sys.exit(2)
for u in call("GET", "/admin/users?statut=en_attente", token=adm["access_token"])[1]:
    if u["email"] in (mail_a, mail_b):
        call("PATCH", f"/admin/users/{u['id']}/valider", token=adm["access_token"])
tok_a = call("POST", "/auth/login/json", {"identifiant": mail_a, "password": pwd})[1]["access_token"]
tok_b = call("POST", "/auth/login/json", {"identifiant": mail_b, "password": pwd})[1]["access_token"]

# ---------------------------------------------------------------- parcelles
print("\n--- Parcelles ---")
s, _ = call("GET", "/parcelles")
check("Liste sans token", s, 401)

payload = {"nom": "Oliveraie Sfax", "culture": "olivier", "surface_ha": 2.5,
           "latitude": 34.74, "longitude": 10.76, "date_plantation": "2015-03-01"}
s, parcelle = call("POST", "/parcelles", payload, tok_a)
check("Créer une parcelle", s, 201)
pid = parcelle["id"] if s == 201 else None
if pid is None:
    print("  détail :", parcelle)
    sys.exit(1)
check("  surface 2.5", parcelle.get("surface_ha"), 2.5)
check("  date de plantation", parcelle.get("date_plantation"), "2015-03-01")

check("Culture invalide", call("POST", "/parcelles", {**payload, "culture": "banane"}, tok_a)[0], 422)
check("Latitude hors limites", call("POST", "/parcelles", {**payload, "latitude": 120}, tok_a)[0], 422)
check("Surface négative", call("POST", "/parcelles", {**payload, "surface_ha": -1}, tok_a)[0], 422)

s, liste = call("GET", "/parcelles", token=tok_a)
check("Lister mes parcelles", (s, any(p["id"] == pid for p in liste)), (200, True))
s, liste = call("GET", "/parcelles?culture=olivier", token=tok_a)
check("Filtre culture=olivier", any(p["id"] == pid for p in liste), True)
s, liste = call("GET", "/parcelles?culture=tomate", token=tok_a)
check("Filtre culture=tomate (aucune)", any(p["id"] == pid for p in liste), False)
check("Lire une parcelle", call("GET", f"/parcelles/{pid}", token=tok_a)[0], 200)

s, maj = call("PATCH", f"/parcelles/{pid}", {"surface_ha": 3}, tok_a)
check("Modifier la surface (PATCH)", s, 200)
check("  surface = 3", maj.get("surface_ha"), 3.0)
check("  nom inchangé", maj.get("nom"), "Oliveraie Sfax")

check("Autre utilisateur : lire", call("GET", f"/parcelles/{pid}", token=tok_b)[0], 404)
check("Autre utilisateur : modifier", call("PATCH", f"/parcelles/{pid}", {"surface_ha": 9}, tok_b)[0], 404)
check("Autre utilisateur : supprimer", call("DELETE", f"/parcelles/{pid}", token=tok_b)[0], 404)

# ---------------------------------------------------------------- conversations
print("\n--- Conversations ---")
s, conv = call("POST", "/conversations", {"parcelle_id": pid}, tok_a)
check("Créer une conversation", s, 201)
cid = conv["id"]
check("Conversation sur la parcelle d'un autre", call("POST", "/conversations", {"parcelle_id": pid}, tok_b)[0], 404)
check("Conversation sur une parcelle inconnue", call("POST", "/conversations", {"parcelle_id": 99999999}, tok_a)[0], 404)

net, sombre = image_bytes("net"), image_bytes("sombre")

s, m1 = question(tok_a, cid, "Pourquoi les feuilles de mon olivier jaunissent ?", [(net, "image/jpeg")])
check("Question en français + 1 photo", s, 201)
photo_url = None
if s == 201:
    check("  langue détectée = fr", m1["message"]["langue"], "fr")
    check("  1 photo enregistrée", len(m1["message"]["photos"]), 1)
    photo_url = m1["message"]["photos"][0]["url"]
    info("  photos_a_reprendre (image nette)", m1["photos_a_reprendre"])
    st, ctype, _ = get_raw(photo_url)
    check("  photo accessible via /uploads", (st, ctype.startswith("image/")), (200, True))
else:
    print("  détail :", m1)

s, m2 = question(tok_a, cid, "علاش أوراق الزيتونة صفرت؟")
check("Question en arabe (sans photo)", s, 201)
if s == 201:
    check("  langue détectée = ar", m2["message"]["langue"], "ar")
    check("  texte arabe conservé", m2["message"]["contenu"], "علاش أوراق الزيتونة صفرت؟")

s, m3 = question(tok_a, cid, "Voici une photo prise de nuit", [(sombre, "image/jpeg")])
check("Question avec photo très sombre", s, 201)
if s == 201:
    info("  photos_a_reprendre (image sombre)", [p.get("probleme") for p in m3["photos_a_reprendre"]] or "aucune")

check("Fichier non image refusé", question(tok_a, cid, "test", [(b"ceci n'est pas une image", "text/plain")])[0], 422)
check("4 photos refusées (max 3)", question(tok_a, cid, "test", [(net, "image/jpeg")] * 4)[0], 422)
s, _ = call("POST", f"/conversations/{cid}/messages", token=tok_a, multipart=build_multipart({}, []))
check("Question absente refusée", s, 422)

s, liste = call("GET", "/conversations", token=tok_a)
mine = [c for c in liste if c["id"] == cid]
check("Lister mes conversations", (s, len(mine)), (200, 1))
check("  nb_messages = 3", mine[0]["nb_messages"] if mine else None, 3)
s, liste = call("GET", f"/conversations?parcelle_id={pid}", token=tok_a)
check("Filtre par parcelle", any(c["id"] == cid for c in liste), True)

s, detail = call("GET", f"/conversations/{cid}", token=tok_a)
check("Détail de la conversation", s, 200)
check("  3 messages", len(detail["messages"]) if s == 200 else None, 3)

check("Autre utilisateur : lire conversation", call("GET", f"/conversations/{cid}", token=tok_b)[0], 404)
check("Autre utilisateur : poser une question", question(tok_b, cid, "intrus")[0], 404)
check("Autre utilisateur : supprimer", call("DELETE", f"/conversations/{cid}", token=tok_b)[0], 404)

s, hist = call("GET", f"/parcelles/{pid}/historique", token=tok_a)
check("Historique de la parcelle", s, 200)
check("  1 conversation, 3 messages", (len(hist), len(hist[0]["messages"])) if s == 200 and hist else None, (1, 3))
check("Autre utilisateur : historique", call("GET", f"/parcelles/{pid}/historique", token=tok_b)[0], 404)

# ---------------------------------------------------------------- nettoyage
print("\n--- Suppressions ---")
check("Supprimer la conversation", call("DELETE", f"/conversations/{cid}", token=tok_a)[0], 204)
if photo_url:
    check("  fichier photo supprimé du disque", get_raw(photo_url)[0], 404)
check("  conversation introuvable ensuite", call("GET", f"/conversations/{cid}", token=tok_a)[0], 404)
check("Supprimer la parcelle", call("DELETE", f"/parcelles/{pid}", token=tok_a)[0], 204)
check("  parcelle introuvable ensuite", call("GET", f"/parcelles/{pid}", token=tok_a)[0], 404)

print(f"\n{sum(results)}/{len(results)} tests réussis")
sys.exit(0 if all(results) else 1)
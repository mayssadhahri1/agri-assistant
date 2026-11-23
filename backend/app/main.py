from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.services.rag.rag_routes import router as rag_router
from .database import get_db
from .routers import auth, conversations, parcelles
from .services.photos import UPLOAD_DIR

app = FastAPI(
    title="Assistant agricole intelligent (VLM + RAG)",
    description="API backend : comptes, parcelles, questions/réponses, base de connaissances.",
    version="0.1.0",
)
app.include_router(rag_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(parcelles.router)
app.include_router(conversations.router)

# Photos accessibles via /uploads/photos/<nom>.jpg
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def _fichiers_en_binary(noeud):
    """Swagger UI n'affiche pas de bouton « Choisir un fichier » pour le format
    OpenAPI 3.1 (contentMediaType). On ajoute format=binary pour qu'il le fasse."""
    if isinstance(noeud, dict):
        if noeud.get("contentMediaType") == "application/octet-stream":
            noeud["format"] = "binary"
        for valeur in noeud.values():
            _fichiers_en_binary(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            _fichiers_en_binary(valeur)


def custom_openapi():
    if not app.openapi_schema:
        schema = FastAPI.openapi(app)
        _fichiers_en_binary(schema)
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/health", tags=["Système"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connectée"}

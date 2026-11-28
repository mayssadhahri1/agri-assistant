from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://root:@localhost:3307/agri_assistant?charset=utf8mb4"
    jwt_secret: str = "dev-secret-a-changer"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # --- Emails (validation des comptes) ---
    # Si smtp_host est vide, les emails ne partent pas : ils sont enregistrés
    # dans backend/emails_dev/ et visibles sur /dev/emails (pratique pour tester).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Assistant agricole <no-reply@agri.tn>"
    # Durée de validité des boutons Accepter / Refuser reçus par l'admin
    decision_lien_heures: int = 72

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

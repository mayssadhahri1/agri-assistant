-- =====================================================================
--  Assistant agricole intelligent (VLM + RAG) - Schéma MySQL / MariaDB
--  Exécuter :  mysql -u root -P 3307 --protocol=TCP < database/schema.sql
-- =====================================================================

CREATE DATABASE IF NOT EXISTS agri_assistant
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;   -- utf8mb4 = support de l'arabe
USE agri_assistant;

-- ---------- F6 : comptes (agriculteur / expert / admin) ----------
CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  nom           VARCHAR(100) NOT NULL,
  email         VARCHAR(150) NULL UNIQUE,
  telephone     VARCHAR(20)  NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role          ENUM('agriculteur','expert','admin') NOT NULL DEFAULT 'agriculteur',
  langue        ENUM('fr','ar') NOT NULL DEFAULT 'fr',
  actif         BOOLEAN NOT NULL DEFAULT TRUE,
  -- Validation du compte par l'administrateur avant la première connexion
  statut        ENUM('en_attente','valide','refuse') NOT NULL DEFAULT 'en_attente',
  valide_par    INT NULL,
  valide_le     DATETIME NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT chk_contact CHECK (email IS NOT NULL OR telephone IS NOT NULL)
) ENGINE=InnoDB;

-- ---------- F5 : parcelles ----------
CREATE TABLE IF NOT EXISTS parcelles (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  user_id          INT NOT NULL,
  nom              VARCHAR(100) NOT NULL,
  culture          ENUM('olivier','tomate','ble','agrumes','palmier_dattier','autre') NOT NULL,
  surface_ha       DECIMAL(10,2) NULL,
  latitude         DECIMAL(9,6) NULL,
  longitude        DECIMAL(9,6) NULL,
  date_plantation  DATE NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- F5 : conversations liées à une parcelle ----------
CREATE TABLE IF NOT EXISTS conversations (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  user_id      INT NOT NULL,
  parcelle_id  INT NULL,
  titre        VARCHAR(200) NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id)     REFERENCES users(id)     ON DELETE CASCADE,
  FOREIGN KEY (parcelle_id) REFERENCES parcelles(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- F1/F4 : messages (question de l'agriculteur / réponse de l'assistant) ----------
CREATE TABLE IF NOT EXISTS messages (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  conversation_id  INT NOT NULL,
  role             ENUM('user','assistant') NOT NULL,
  contenu          TEXT NOT NULL,
  langue           ENUM('fr','ar') NULL,
  diagnostic       VARCHAR(200) NULL,
  confiance        FLOAT NULL,             -- 0..1
  temps_reponse_ms INT NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- F1 : photos (jusqu'à 3 par question) ----------
CREATE TABLE IF NOT EXISTS photos (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  message_id  INT NOT NULL,
  chemin      VARCHAR(255) NOT NULL,
  qualite_ok  BOOLEAN NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- F2/F8 : documents de la base de connaissances ----------
CREATE TABLE IF NOT EXISTS documents (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  titre        VARCHAR(255) NOT NULL,
  fichier      VARCHAR(255) NOT NULL,
  type         ENUM('pdf','docx','web') NOT NULL,
  culture      VARCHAR(50) NULL,
  theme        VARCHAR(100) NULL,
  langue       ENUM('fr','ar') NULL,
  region       VARCHAR(100) NULL,
  statut       ENUM('en_attente','indexe','erreur') NOT NULL DEFAULT 'en_attente',
  nb_chunks    INT NOT NULL DEFAULT 0,
  uploaded_by  INT NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- F2 : sources citées dans une réponse ----------
CREATE TABLE IF NOT EXISTS message_sources (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  message_id   INT NOT NULL,
  document_id  INT NOT NULL,
  page         INT NULL,
  extrait      TEXT NULL,
  FOREIGN KEY (message_id)  REFERENCES messages(id)  ON DELETE CASCADE,
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- F7 : avis de l'agriculteur ----------
CREATE TABLE IF NOT EXISTS feedbacks (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  message_id   INT NOT NULL,
  user_id      INT NOT NULL,
  utile        BOOLEAN NOT NULL,
  commentaire  TEXT NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- F7 : validation par un expert ----------
CREATE TABLE IF NOT EXISTS expert_validations (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  message_id   INT NOT NULL,
  expert_id    INT NULL,
  statut       ENUM('en_attente','valide','corrige','rejete') NOT NULL DEFAULT 'en_attente',
  correction   TEXT NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
  FOREIGN KEY (expert_id)  REFERENCES users(id)    ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- F3 : traçabilité des appels d'outils par l'agent ----------
CREATE TABLE IF NOT EXISTS agent_traces (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  message_id  INT NOT NULL,
  ordre       INT NOT NULL,
  outil       ENUM('maladie','vlm','rag','meteo','historique') NOT NULL,
  entree      TEXT NULL,
  sortie      TEXT NULL,
  duree_ms    INT NULL,
  succes      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
) ENGINE=InnoDB;

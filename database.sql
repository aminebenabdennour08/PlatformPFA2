-- ============================================
-- PNEUMOANALYST - BASE DE DONNÉES MÉDICALE
-- ============================================

-- Créer la base de données
CREATE DATABASE IF NOT EXISTS pfe_medical;
USE pfe_medical;

-- ============================================
-- TABLE DES UTILISATEURS (médecins)
-- ============================================
DROP TABLE IF EXISTS users;
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    specialty VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE DES CONSULTATIONS (principale)
-- ============================================
DROP TABLE IF EXISTS consultations;
CREATE TABLE IF NOT EXISTS consultations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    consultation_id VARCHAR(50),
    patient_id VARCHAR(50),
    patient_name VARCHAR(100) NOT NULL,
    patient_age INT,
    patient_gender CHAR(1),
    smoking_status ENUM('never', 'former', 'current'),
    smoking_years INT,
    packs_per_day DECIMAL(3,1),
    pack_years DECIMAL(5,1),
    passive_smoking BOOLEAN,
    clinical_suspicion ENUM('low', 'moderate', 'high', 'very_high'),
    urgency_level ENUM('low', 'medium', 'high', 'critical'),
    initial_suspicion TEXT,
    clinical_notes TEXT,
    symptoms JSON,
    image_path VARCHAR(500),
    vit_results JSON,
    staging JSON,
    final_diagnosis JSON,
    additional_tests JSON,
    additional_tests_results JSON,
    status VARCHAR(50) DEFAULT 'consultation_completed',
    direct_validation BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_patient_name (patient_name),
    INDEX idx_patient_id (patient_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- ============================================
-- TABLE DES PATIENTS (ancienne structure)
-- ============================================
DROP TABLE IF EXISTS patients;
CREATE TABLE IF NOT EXISTS patients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    date_naissance DATE,
    sexe CHAR(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE DES EXAMENS (ancienne structure)
-- ============================================
DROP TABLE IF EXISTS examens;
CREATE TABLE IF NOT EXISTS examens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    date_examen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    classe_predite VARCHAR(50),
    confidence DECIMAL(5,4),
    statut ENUM('en_attente', 'valide', 'rejete') DEFAULT 'en_attente',
    classe_validee VARCHAR(50),
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

-- ============================================
-- TABLE DES NOTES CLINIQUES
-- ============================================
DROP TABLE IF EXISTS clinical_notes;
CREATE TABLE IF NOT EXISTS clinical_notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    examen_id INT NOT NULL,
    note_texte TEXT,
    date_note TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (examen_id) REFERENCES examens(id) ON DELETE CASCADE
);

-- ============================================
-- TABLE DES ANNOTATIONS
-- ============================================
DROP TABLE IF EXISTS annotations;
CREATE TABLE IF NOT EXISTS annotations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    examen_id INT NOT NULL,
    coord_x INT,
    coord_y INT,
    largeur INT,
    hauteur INT,
    classe_annotee VARCHAR(50),
    date_annotation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (examen_id) REFERENCES examens(id) ON DELETE CASCADE
);

-- ============================================
-- INSERTION D'UN UTILISATEUR DE TEST
-- ============================================
-- Mot de passe: 'password123' (à hasher dans l'application)
INSERT INTO users (username, email, full_name, specialty, password_hash) 
VALUES ('doctor', 'doctor@hospital.com', 'Dr. Demo', 'Pneumologie', 'pbkdf2:sha256:600000$1234567890abcdef')
ON DUPLICATE KEY UPDATE username = username;

-- ============================================
-- AFFICHAGE DES TABLES CRÉÉES
-- ============================================
SHOW TABLES;

-- ============================================
-- COMPTER LES ENREGISTREMENTS
-- ============================================
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'consultations', COUNT(*) FROM consultations
UNION ALL
SELECT 'patients', COUNT(*) FROM patients
UNION ALL
SELECT 'examens', COUNT(*) FROM examens
UNION ALL
SELECT 'clinical_notes', COUNT(*) FROM clinical_notes
UNION ALL
SELECT 'annotations', COUNT(*) FROM annotations;
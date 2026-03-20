-- =========================
-- INIT.SQL - RaketOwl
-- Full layout with internal collaboration
-- =========================

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS raketowl;
USE raketowl;

-- =========================
-- USERS TABLE
-- =========================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('admin', 'editor') NOT NULL DEFAULT 'editor',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Initial admin user
INSERT INTO users (username, password, role) VALUES (
    'admin',
    'scrypt:32768:8:1$RPwf3n4vd0kOFUR4$42fa4d1abe85b25994b9362fc282f5ff079e68f56b3815c2414411307600cefbc3efe033b61e286f2b5793f1472c7b0c3b869ad8b4972354ffabc3042183bbaa',
    'admin'
);

-- =========================
-- DOCUMENTS TABLE
-- =========================
CREATE TABLE IF NOT EXISTS documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    filepath VARCHAR(255) NOT NULL,
    owner_id INT NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    version INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =========================
-- DOCUMENT SHARING TABLE
-- For internal collaboration (shared documents with users)
-- =========================
CREATE TABLE IF NOT EXISTS document_shares (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    shared_with_user_id INT NOT NULL,
    permission ENUM('view','edit') DEFAULT 'view',

    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =========================
-- ACTIVITY LOGS TABLE
-- =========================
CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),
    action VARCHAR(100),
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- OPTIONAL: Example internal sharing (for testing)
-- =========================
-- Uncomment if you have users and documents to test sharing
-- INSERT INTO document_shares (document_id, shared_with_user_id, permission)
-- VALUES
--     (1, 2, 'view'),   -- User 2 can view document 1
--     (1, 3, 'edit');   -- User 3 can edit document 1

SET FOREIGN_KEY_CHECKS=0;

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
-- GROUPS MASTER TABLE
-- =========================
CREATE TABLE IF NOT EXISTS groups_master (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- USER-GROUP MAPPING TABLE
-- =========================
CREATE TABLE IF NOT EXISTS user_groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    group_id INT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups_master(id) ON DELETE CASCADE,

    UNIQUE KEY unique_user_group (user_id, group_id)
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


SET FOREIGN_KEY_CHECKS=1;

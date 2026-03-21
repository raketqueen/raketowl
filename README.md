# 📂 RaketOwl Filing Cabinet

A Dockerized document management system built with:

- Flask (Backend)
- MySQL (Database)
- Nginx (Reverse Proxy)
- Bootstrap (Frontend UI)

---

## 🚀 Features

- User authentication (login/logout)
- File upload & download
- Private & public document visibility
- Activity logging
- Dark / Light theme UI

---

## 🐳 Run with Docker

### 1. Clone the repository

```bash
git clone https://github.com/raketqueen/raketowl.git
cd ~/raketowl
```

### 2. Build the Docker containers:

```bash
docker compose up --build -d
```

### 3. Initial Admin Account
- Username: admin
- Password: admin123 (hashed in init.sql)

### 4. Stopping containers

```bash
docker compose down
```

# Author
- Rommel Asis - Original Developer
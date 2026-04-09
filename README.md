# 📂 RaketOwl Filing Cabinet (Under Development - Alpha)

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
- Private document collaboration via user or group (Enforce Permission)
- User and Group management UI
- Version control system
- Activity logging (with sorting and color code feature)
- Dark / Light theme UI accross pages

---

## 🏗️ In Development

- User View/Edit permission (POC testing)
- Group View/Edit permission (POC testing)
- UI alignment and column polishing
- Added the last user modified the file
- Hold Document Locking Feature (Check-in/Check-out Capability)
- User level password reset

---

## 🌐 Project Structure
```
raketowl/
|-------app/                        # Flask app
|        |----app.py                # Flask app routes & logic
|        |----Dockerfile
|        |----requirements.txt
|        |----templates/            # HTML templates
|              |----index.html
|              |----admin_logs.html
|              |----admin_users.html
|              |----edit_user.html
|-------nginx/                      # Nginx config
|        |----Dockerfile
|        |----nginx.conf
|        |----413.html              # Oversize file notification page
|-------docker-compose.yml          # Docker Compose file
|-------init.sql                    # Initial MySQL setup & hashed admin password
|-------README.md
|-------.gitignore
```

---

## 🛠️ Future Improvements

- Hierarchical Structure
- Attribute assignment (adding metadata to the file uploaded)

---

## 🔩 Requirements
- Docker
- Docker Compose
- Web browser (Chrome, Firefox, etc.)

# 🐳 Run with Docker

### 1. Clone the repository

```bash
git clone https://github.com/raketqueen/raketowl.git
cd ~/raketowl
```

### 2. Build the Docker containers:

```bash
docker compose up --build -d
```
### 3. Post Docker Compose build:
- Web app will be accessible at http://localhost:8080
- Username: admin
- Password: admin123 (hashed in init.sql)

### 4. Stopping containers

```bash
docker compose down
```

# Author
- Rommel Asis - Original Developer
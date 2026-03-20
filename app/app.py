import os
from flask import Flask, render_template, request, redirect, session, url_for, send_file
import mysql.connector
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'K0rgG3#5952'  # change in production


# External document storage (Docker volume)
DOCUMENTS_PATH = '/documents'
app.config['DOCUMENTS_PATH'] = DOCUMENTS_PATH

if not os.path.exists(DOCUMENTS_PATH):
    os.makedirs(DOCUMENTS_PATH)

# =========================
# DATABASE CONNECTION
# =========================


def get_db_connection():
    return mysql.connector.connect(
        host='db',
        user='root',
        password='ThunderKats1973',
        database='raketowl'
    )

# =========================
# HOME PAGE
# =========================


@app.route('/')
def index():
    error = request.args.get('error')
    search = request.args.get('search')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if 'user_id' in session:
        # Logged in user

        if search:
            cursor.execute(
                """SELECT documents.id, documents.filename, documents.version, documents.owner_id, documents.is_public, users.username 
                   FROM documents
                   JOIN users ON documents.owner_id = users.id
                   WHERE documents.owner_id = %s AND documents.filename LIKE %s""",
                (session['user_id'], f"%{search}%")
            )
        else:
            cursor.execute(
                """SELECT documents.id, documents.filename, documents.version, documents.owner_id, documents.is_public, users.username 
                   FROM documents
                   JOIN users ON documents.owner_id = users.id
                   WHERE documents.owner_id = %s""",
                (session['user_id'],)
            )

    else:
        # Public view

        if search:
            cursor.execute(
                """SELECT documents.id, documents.filename, documents.version, documents.owner_id, documents.is_public, users.username 
                   FROM documents
                   JOIN users ON documents.owner_id = users.id
                   WHERE documents.is_public = 1 AND documents.filename LIKE %s""",
                (f"%{search}%",)
            )
        else:
            cursor.execute(
                """SELECT documents.id, documents.filename, documents.version, documents.owner_id, documents.is_public, users.username 
                   FROM documents
                   JOIN users ON documents.owner_id = users.id
                   WHERE documents.is_public = 1"""
            )

    documents = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html', documents=documents, error=error)

# =========================
# LOGIN
# =========================


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']

        # Log activity
        cursor.execute(
            "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
            (username, 'LOGIN', 'User logged in')
        )
        conn.commit()

        return redirect(url_for('index'))
    else:
        return redirect(url_for('index', error='invalid'))

# =========================
# LOGOUT
# =========================


@app.route('/logout')
def logout():
    username = session.get('username')

    if username:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
            (username, 'LOGOUT', 'User logged out')
        )
        conn.commit()

        cursor.close()
        conn.close()

    session.clear()
    return redirect(url_for('index'))

# =========================
# UPLOAD DOCUMENT
# =========================


@app.route('/upload', methods=['POST'])
def upload():

    if 'user_id' not in session:
        return redirect(url_for('index'))

    file = request.files.get('document')

    if not file or file.filename == '':
        return "No file selected", 400

    filename = file.filename
    is_public = 1 if request.form.get('is_public') == 'on' else 0

    # Save file to external storage
    filepath = os.path.join(app.config['DOCUMENTS_PATH'], filename)
    file.save(filepath)

    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ INSERT aligned with your schema
    cursor.execute(
        """INSERT INTO documents 
        (filename, filepath, owner_id, version, is_public) 
        VALUES (%s, %s, %s, %s, %s)""",
        (filename, filepath, session['user_id'], 1, is_public)
    )

    # Activity log
    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (session['username'], 'UPLOAD', f'Uploaded {filename}')
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('index'))

# =========================
# DOWNLOAD DOCUMENT
# =========================


@app.route('/download/<int:doc_id>')
def download(doc_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT filename, filepath, owner_id, is_public FROM documents WHERE id = %s",
        (doc_id,)
    )
    doc = cursor.fetchone()

    cursor.close()
    conn.close()

    if not doc:
        return "File not found", 404

    # Access control
    if not doc['is_public']:
        if 'user_id' not in session or session['user_id'] != doc['owner_id']:
            return "Unauthorized", 403

    return send_file(doc['filepath'], as_attachment=True)

# =========================
# DELETE DOCUMENT
# =========================


@app.route('/delete/<int:doc_id>', methods=['POST'])
def delete_document(doc_id):

    if 'user_id' not in session:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT filepath, owner_id, filename FROM documents WHERE id = %s",
        (doc_id,)
    )
    doc = cursor.fetchone()

    if not doc:
        cursor.close()
        conn.close()
        return "File not found", 404

    # Only owner can delete
    if doc['owner_id'] != session['user_id']:
        cursor.close()
        conn.close()
        return "Unauthorized", 403

    # Delete file from storage
    if os.path.exists(doc['filepath']):
        os.remove(doc['filepath'])

    # Delete from DB
    cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))

    # Log activity
    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (session['username'], 'DELETE', f"Deleted {doc['filename']}")
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('index'))

# =========================
# TOGGLE PUBLIC / PRIVATE
# =========================


@app.route('/toggle_visibility/<int:doc_id>', methods=['POST'])
def toggle_visibility(doc_id):

    if 'user_id' not in session:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get document
    cursor.execute(
        "SELECT is_public, owner_id, filename FROM documents WHERE id = %s",
        (doc_id,)
    )
    doc = cursor.fetchone()

    if not doc:
        cursor.close()
        conn.close()
        return "File not found", 404

    # Only owner can modify
    if doc['owner_id'] != session['user_id']:
        cursor.close()
        conn.close()
        return "Unauthorized", 403

    # Toggle value
    new_status = 0 if doc['is_public'] else 1

    cursor.execute(
        "UPDATE documents SET is_public = %s WHERE id = %s",
        (new_status, doc_id)
    )

    # Log activity
    action_text = "Made Public" if new_status == 1 else "Made Private"
    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (session['username'], 'VISIBILITY_CHANGE',
         f"{action_text}: {doc['filename']}")
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('index'))


# =========================
# RUN APP
# =========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

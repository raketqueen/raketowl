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
                """
                SELECT DISTINCT
                    documents.id,
                    documents.filename,
                    documents.version,
                    documents.owner_id,
                    documents.is_public,
                    users.username,
                    document_shares.permission
                FROM documents
                JOIN users ON documents.owner_id = users.id
                LEFT JOIN document_shares
                    ON documents.id = document_shares.document_id
                WHERE
                    (
                        documents.owner_id = %s
                        OR documents.is_public = 1
                        OR document_shares.shared_with_user_id = %s
                    )
                    AND documents.filename LIKE %s
                """,
                (session['user_id'], session['user_id'], f"%{search}%")
            )
        else:
            cursor.execute(
                """
                SELECT DISTINCT
                    documents.id,
                    documents.filename,
                    documents.version,
                    documents.owner_id,
                    documents.is_public,
                    users.username,
                    document_shares.permission
                FROM documents
                JOIN users ON documents.owner_id = users.id
                LEFT JOIN document_shares
                    ON documents.id = document_shares.document_id
                WHERE
                    documents.owner_id = %s
                    OR documents.is_public = 1
                    OR document_shares.shared_with_user_id = %s
                """,
                (session['user_id'], session['user_id'])
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

        if 'user_id' not in session:
            return "Unauthorized", 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if shared
        cursor.execute(
            """
            SELECT permission FROM document_shares
            WHERE document_id = %s AND shared_with_user_id = %s
            """,
            (doc_id, session['user_id'])
        )
        shared = cursor.fetchone()

        cursor.close()
        conn.close()

        if session['user_id'] != doc['owner_id'] and not shared:
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
# ADMIN - VIEW USERS
# =========================


@app.route('/admin/users')
def admin_users():

    # Only admin allowed
    if 'user_id' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get users
    cursor.execute("SELECT id, username, role, created_at FROM users")
    users = cursor.fetchall()

    # Get groups
    cursor.execute("SELECT id, name, description FROM groups_master")
    groups = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_users.html', users=users, groups=groups)

# =========================
# ADMIN - CREATE GROUP
# =========================


@app.route('/admin/create_group', methods=['POST'])
def create_group():

    # Admin only
    if 'user_id' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403

    group_name = request.form.get('group_name')
    description = request.form.get('description')

    if not group_name:
        return redirect(url_for('admin_users'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO groups_master (name, description) VALUES (%s, %s)",
            (group_name, description)
        )
        conn.commit()

        # Log activity
        cursor.execute(
            "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
            (session['username'], 'CREATE_GROUP',
             f"Created group: {group_name}")
        )
        conn.commit()

    except Exception as e:
        print("Error creating group:", e)

    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# =========================
# ADMIN - EDIT GROUP
# =========================


@app.route('/admin/edit_group/<int:group_id>', methods=['POST'])
def edit_group(group_id):

    if 'user_id' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403

    group_name = request.form.get('group_name')
    description = request.form.get('description')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get old group name
    cursor.execute("SELECT name FROM groups_master WHERE id = %s", (group_id,))
    old_name = cursor.fetchone()[0]

    # Update group
    cursor.execute(
        "UPDATE groups_master SET name = %s, description = %s WHERE id = %s",
        (group_name, description, group_id)
    )

    # Log activity with name
    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (
            session['username'],
            'EDIT_GROUP',
            f"Edited group: {old_name} → {group_name}"
        )
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# =========================
# ADMIN - DELETE GROUP (STRICT)
# =========================


@app.route('/admin/delete_group/<int:group_id>', methods=['POST'])
def delete_group(group_id):

    if 'user_id' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔍 CHECK if group is used
    cursor.execute(
        "SELECT COUNT(*) FROM user_groups WHERE group_id = %s",
        (group_id,)
    )
    count = cursor.fetchone()[0]

    if count > 0:
        cursor.close()
        conn.close()
        return "Cannot delete group: group is assigned to users", 400

    # Get group name BEFORE delete
    cursor.execute("SELECT name FROM groups_master WHERE id = %s", (group_id,))
    group = cursor.fetchone()

    group_name = group[0] if group else "Unknown"

    # Delete group
    cursor.execute(
        "DELETE FROM groups_master WHERE id = %s",
        (group_id,)
    )

    # Log activity with name
    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (
            session['username'],
            'DELETE_GROUP',
            f"Deleted group: {group_name}"
        )
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# =========================
# ADMIN - ACTIVITY LOGS
# =========================


@app.route('/admin/logs')
def admin_logs():

    # Only admin allowed
    if 'user_id' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            username, 
            action, 
            details, 
            CONVERT_TZ(timestamp, '+00:00', '+08:00') AS timestamp
        FROM activity_logs
        ORDER BY timestamp DESC
    """)
    logs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_logs.html', logs=logs)


# =========================
# RUN APP
# =========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

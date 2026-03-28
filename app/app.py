import os
from flask import Flask, render_template, request, redirect, session, url_for, send_file, flash
import mysql.connector
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'K0rgG3#5952'  # change in production


# External document storage (Docker volume)
DOCUMENTS_PATH = '/documents'
app.config['DOCUMENTS_PATH'] = DOCUMENTS_PATH

if not os.path.exists(DOCUMENTS_PATH):
    raise Exception("❌ Documents volume not mounted! Check docker-compose.")

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

    all_users = []  # Initialize in case user not logged in

    if 'user_id' in session:
        # Fetch all users except the current user for the share dropdown
        cursor.execute(
            "SELECT id, username FROM users WHERE id != %s", (session['user_id'],))
        all_users = cursor.fetchall()

        # Logged in user: fetch documents
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
                SELECT
                    documents.id,
                    documents.filename,
                    documents.version,
                    documents.owner_id,
                    documents.is_public,
                    users.username,
                    MAX(document_shares.permission) AS permission
                FROM documents
                JOIN users ON documents.owner_id = users.id
                LEFT JOIN document_shares
                    ON documents.id = document_shares.document_id
                WHERE
                    documents.owner_id = %s
                    OR documents.is_public = 1
                    OR document_shares.shared_with_user_id = %s
                GROUP BY documents.id
                """,
                (session['user_id'], session['user_id'])
            )
    else:
        # Public view only
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

    # =========================
    # FETCH SHARING INFO
    # =========================

    shared_map = {}

    if 'user_id' in session:

        conn2 = get_db_connection()
        cursor2 = conn2.cursor(dictionary=True)

        cursor2.execute("""
            SELECT 
                ds.document_id,
                ds.shared_with_user_id,
                u.username,
                ds.permission
            FROM document_shares ds
            JOIN users u ON ds.shared_with_user_id = u.id
            WHERE ds.document_id IN (
                SELECT id FROM documents WHERE owner_id = %s
            )
        """, (session['user_id'],))

        shares = cursor2.fetchall()

        # Build mapping: {doc_id: ["user (perm)", ...]}
        for s in shares:
            doc_id = s['document_id']
            entry = {
                "display": f"{s['username']} ({s['permission']})",
                "user_id": s['shared_with_user_id']
            }

            if doc_id not in shared_map:
                shared_map[doc_id] = []

            shared_map[doc_id].append(entry)

        cursor2.close()
        conn2.close()

    cursor.close()
    conn.close()

    return render_template(
        'index.html',
        documents=documents,
        error=error,
        shared_map=shared_map,
        all_users=all_users
    )

# =========================
# UNSHARE DOCUMENT (USER)
# =========================


@app.route('/unshare/<int:doc_id>', methods=['POST'])
def unshare_document(doc_id):

    if 'user_id' not in session:
        return redirect(url_for('index'))

    try:
        target_user_id = int(request.form.get('user_id'))
    except (TypeError, ValueError):
        flash("Invalid user", "warning")
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check ownership
    cursor.execute(
        "SELECT owner_id, filename FROM documents WHERE id = %s",
        (doc_id,)
    )
    doc = cursor.fetchone()

    if not doc:
        cursor.close()
        conn.close()
        flash("Document not found", "danger")
        return redirect(url_for('index'))

    owner_id, filename = doc

    if owner_id != session['user_id']:
        cursor.close()
        conn.close()
        flash("Unauthorized", "danger")
        return redirect(url_for('index'))

    # Delete share
    cursor.execute(
        """
        DELETE FROM document_shares
        WHERE document_id = %s AND shared_with_user_id = %s
        """,
        (doc_id, target_user_id)
    )

    # Log
    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (
            session['username'],
            'UNSHARE_DOCUMENT',
            f"Removed access for user_id={target_user_id} from '{filename}'"
        )
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('index'))

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
    filepath = os.path.join(app.config['DOCUMENTS_PATH'], filename)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # =========================
    # STEP 1: CHECK IF DOCUMENT EXISTS (BY FILENAME)
    # =========================
    cursor.execute(
        """
        SELECT id, owner_id, version
        FROM documents
        WHERE filename = %s
        """,
        (filename,)
    )
    doc = cursor.fetchone()

    if doc:
        doc_id = doc['id']
        owner_id = doc['owner_id']
        current_version = doc['version']

        # =========================
        # STEP 2: CHECK PERMISSION
        # =========================

        is_owner = (session['user_id'] == owner_id)

        cursor.execute(
            """
            SELECT permission FROM document_shares
            WHERE document_id = %s AND shared_with_user_id = %s
            """,
            (doc_id, session['user_id'])
        )
        share = cursor.fetchone()

        has_edit_permission = share and share['permission'] == 'edit'

        # =========================
        # STEP 3: AUTHORIZE
        # =========================

        if not is_owner and not has_edit_permission:
            cursor.close()
            conn.close()
            flash("You only have VIEW access. Upload not allowed.", "warning")
            return redirect(url_for('index'))

        # =========================
        # STEP 4: UPDATE DOCUMENT (VERSIONING)
        # =========================

        new_version = current_version + 1

        # Overwrite file
        file.save(filepath)

        cursor.execute(
            """
            UPDATE documents
            SET version = %s, filepath = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (new_version, filepath, doc_id)
        )

        action_text = f"Updated '{filename}' to version {new_version}"

    else:
        # =========================
        # NEW DOCUMENT (OWNER ONLY)
        # =========================

        file.save(filepath)

        cursor.execute(
            """
            INSERT INTO documents 
            (filename, filepath, owner_id, version, is_public)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (filename, filepath, session['user_id'], 1, 0)
        )

        action_text = f"Uploaded new file '{filename}'"

    # =========================
    # ACTIVITY LOG
    # =========================

    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (session['username'], 'UPLOAD', action_text)
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
# SHARE DOCUMENT WITH USER
# =========================


@app.route('/share/<int:doc_id>', methods=['POST'])
def share_document(doc_id):

    if 'user_id' not in session:
        return redirect(url_for('index'))

    try:
        shared_user_id = int(request.form.get('user_id'))
    except (TypeError, ValueError):
        flash("Invalid user selected", "warning")
        return redirect(url_for('index'))

    permission = request.form.get('permission', 'view')  # default to 'view'

    # Prevent sharing with self
    if shared_user_id == session['user_id']:
        flash("You cannot share a document with yourself", "warning")
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the user exists
    cursor.execute(
        "SELECT id, username FROM users WHERE id = %s", (shared_user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        flash("Selected user does not exist", "warning")
        return redirect(url_for('index'))

    # Check ownership of the document
    cursor.execute(
        "SELECT owner_id, filename FROM documents WHERE id = %s",
        (doc_id,)
    )
    doc = cursor.fetchone()
    if not doc:
        cursor.close()
        conn.close()
        flash("Document does not exist", "warning")
        return redirect(url_for('index'))

    owner_id, filename = doc
    if owner_id != session['user_id']:
        cursor.close()
        conn.close()
        flash("Unauthorized: You are not the owner", "danger")
        return redirect(url_for('index'))

    # Prevent duplicate share
    cursor.execute(
        """
        SELECT id FROM document_shares
        WHERE document_id = %s AND shared_with_user_id = %s
        """,
        (doc_id, shared_user_id)
    )
    existing = cursor.fetchone()

    if existing:
        # Update permission instead
        cursor.execute(
            """
            UPDATE document_shares
            SET permission = %s
            WHERE document_id = %s AND shared_with_user_id = %s
            """,
            (permission, doc_id, shared_user_id)
        )
    else:
        # Insert new share
        cursor.execute(
            """
            INSERT INTO document_shares (document_id, shared_with_user_id, permission)
            VALUES (%s, %s, %s)
            """,
            (doc_id, shared_user_id, permission)
        )

    # Log activity
    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (
            session['username'],
            'SHARE_DOCUMENT',
            f"Shared '{filename}' with user_id={shared_user_id} ({permission})"
        )
    )

    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Document '{filename}' shared successfully", "success")
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

    # Get users with groups (JOIN + GROUP_CONCAT)
    cursor.execute("""
        SELECT 
            u.id,
            u.username,
            u.role,
            u.created_at,
            GROUP_CONCAT(g.name SEPARATOR ', ') AS user_groups
        FROM users u
        LEFT JOIN user_groups ug ON u.id = ug.user_id
        LEFT JOIN groups_master g ON ug.group_id = g.id
        GROUP BY u.id
    """)

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

        flash(f"Group '{group_name}' created", "success")

        # Log activity
        cursor.execute(
            "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
            (session['username'], 'CREATE_GROUP',
             f"Created group: {group_name}")
        )
        conn.commit()

    except Exception as e:
        flash("Error: Group may already exist", "warning")

    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# =========================
# ADMIN - CREATE USER
# =========================


@app.route('/admin/create_user', methods=['POST'])
def create_user():

    # Admin only
    if 'user_id' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403

    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    group_ids = request.form.getlist('groups')  # MULTI-SELECT

    if not username or not password:
        return redirect(url_for('admin_users'))

    from werkzeug.security import generate_password_hash
    hashed_password = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert user
    from mysql.connector import Error

    try:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (username, hashed_password, role)
        )
        user_id = cursor.lastrowid

    except Error as e:
        if e.errno == 1062:  # Duplicate entry
            flash("Error: Username already exists", "warning")
            cursor.close()
            conn.close()
            return redirect(url_for('admin_users'))
        else:
            raise

    # Insert user-group mapping
    for group_id in group_ids:
        cursor.execute(
            "INSERT INTO user_groups (user_id, group_id) VALUES (%s, %s)",
            (user_id, group_id)
        )

    # Log activity
    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (
            session['username'],
            'CREATE_USER',
            f"Created user: {username}"
        )
    )

    flash(f"User '{username}' created successfully", "success")

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# =========================
# ADMIN - EDIT USER
# =========================


@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    # Admin only
    if 'user_id' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # POST = update user info
        username = request.form.get('username')
        role = request.form.get('role')
        group_ids = request.form.getlist('groups')
        new_password = request.form.get('password')

        # Update username and role
        cursor.execute(
            "UPDATE users SET username = %s, role = %s WHERE id = %s",
            (username, role, user_id)
        )

        # 🔐 RESET PASSWORD (ONLY IF PROVIDED)
        if new_password:
            from werkzeug.security import generate_password_hash
            hashed_password = generate_password_hash(new_password)

            cursor.execute(
                "UPDATE users SET password = %s WHERE id = %s",
                (hashed_password, user_id)
            )

            # Log password reset
            cursor.execute(
                "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
                (
                    session['username'],
                    'RESET_PASSWORD',
                    f"Reset password for user: {username}"
                )
            )

            flash(f"Password reset for '{username}'", "info")

        # Update user_groups
        cursor.execute(
            "DELETE FROM user_groups WHERE user_id = %s", (user_id,))
        for group_id in group_ids:
            cursor.execute(
                "INSERT INTO user_groups (user_id, group_id) VALUES (%s, %s)",
                (user_id, group_id)
            )

        # Log activity
        cursor.execute(
            "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
            (
                session['username'],
                'EDIT_USER',
                f"Edited user: {username}"
            )
        )

        flash(f"User '{username}' updated successfully", "success")

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('admin_users'))

    else:
        # GET = show edit form
        cursor.execute(
            "SELECT id, username, role FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        cursor.execute(
            "SELECT group_id FROM user_groups WHERE user_id = %s", (user_id,))
        user_group_ids = [row['group_id'] for row in cursor.fetchall()]

        cursor.execute("SELECT id, name FROM groups_master")
        groups = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('edit_user.html', user=user, groups=groups, user_group_ids=user_group_ids)

# =========================
# ADMIN - DELETE USER
# =========================


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):

    # Admin only
    if 'user_id' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403

    # Prevent self-delete (VERY IMPORTANT)
    if user_id == session['user_id']:
        return "You cannot delete your own account", 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get username BEFORE delete (for logs)
    cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return "User not found", 404

    username_to_delete = user[0]

    # Delete user (CASCADE will clean user_groups)
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

    # Log activity
    cursor.execute(
        "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)",
        (
            session['username'],
            'DELETE_USER',
            f"Deleted user: {username_to_delete}"
        )
    )

    flash(f"User '{username_to_delete}' deleted", "warning")

    conn.commit()
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
        flash("Cannot delete group: group is assigned to users", "warning")
        return redirect(url_for('admin_users'))

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

    flash(f"Group '{group_name}' deleted", "warning")

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

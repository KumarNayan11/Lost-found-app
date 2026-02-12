from flask import Flask, render_template, request, redirect, url_for, g, session, flash
import sqlite3
from datetime import datetime
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Generate random secret key for sessions
DATABASE = 'lostfound.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                contact TEXT NOT NULL,
                status TEXT NOT NULL,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_found TIMESTAMP NULL
            )
        ''')
        db.commit()

def search_items(query=''):
    """Reusable search function for both admin and user panels"""
    db = get_db()
    cursor = db.cursor()
    if query:
        param = f'%{query}%'
        cursor.execute('''
            SELECT id, name, description, contact, status, date_added, date_found
            FROM items
            WHERE name LIKE ? OR description LIKE ? OR contact LIKE ?
            ORDER BY id DESC
        ''', (param, param, param))
    else:
        cursor.execute('SELECT id, name, description, contact, status, date_added, date_found FROM items ORDER BY id DESC')
    return cursor.fetchall()

# ============= LANDING & ROLE MANAGEMENT =============

@app.route('/')
def landing():
    """Landing page for role selection"""
    return render_template('landing.html')

@app.route('/set-role/<role>')
def set_role(role):
    """Set user role in session"""
    if role in ['admin', 'user']:
        session['role'] = role
        flash(f'Switched to {role.title()} Panel', 'success')
        return redirect(url_for(f'{role}_dashboard'))
    return redirect(url_for('landing'))

# ============= ADMIN PANEL ROUTES =============

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard with full controls"""
    search_query = request.args.get('search', '').strip()
    items = search_items(search_query)
    return render_template('admin_dashboard.html', items=items, search=search_query)

@app.route('/admin/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    """Delete individual item (admin only)"""
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'error')
        return redirect(url_for('landing'))
    
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM items WHERE id = ?', (item_id,))
        db.commit()
        flash('Item deleted successfully', 'success')
    except sqlite3.Error as e:
        flash('Error deleting item', 'error')
        app.logger.error(f'Database error: {e}')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/clear', methods=['POST'])
def clear_all():
    """Clear all items from database (admin only)"""
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'error')
        return redirect(url_for('landing'))
    
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM items')
        db.commit()
        flash('All items cleared from database', 'success')
    except sqlite3.Error as e:
        flash('Error clearing database', 'error')
        app.logger.error(f'Database error: {e}')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/mark-found/<int:item_id>', methods=['POST'])
def admin_mark_found(item_id):
    """Mark item as found (admin panel)"""
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'error')
        return redirect(url_for('landing'))
    
    try:
        db = get_db()
        cursor = db.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE items
            SET status = 'Found',
                date_found = ?
            WHERE id = ?
        ''', (now, item_id))
        db.commit()
        flash('Item marked as found', 'success')
    except sqlite3.Error as e:
        flash('Error updating item', 'error')
        app.logger.error(f'Database error: {e}')
    
    return redirect(url_for('admin_dashboard'))

# ============= USER PANEL ROUTES =============

@app.route('/user')
def user_dashboard():
    """User dashboard (view-only)"""
    search_query = request.args.get('search', '').strip()
    items = search_items(search_query)
    return render_template('user_dashboard.html', items=items, search=search_query)

@app.route('/user/add', methods=['GET', 'POST'])
def add_item():
    """Add new lost item (user panel)"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        contact = request.form.get('contact', '').strip()
        
        # Basic validation
        if not name or not description or not contact:
            flash('All fields are required', 'error')
            return render_template('add_item.html')
        
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                'INSERT INTO items (name, description, contact, status) VALUES (?, ?, ?, ?)',
                (name, description, contact, 'Lost')
            )
            db.commit()
            flash('Item reported successfully!', 'success')
            return redirect(url_for('user_dashboard'))
        except sqlite3.Error as e:
            flash('Error saving item', 'error')
            app.logger.error(f'Database error: {e}')
            return render_template('add_item.html')
    
    return render_template('add_item.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

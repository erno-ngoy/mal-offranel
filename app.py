from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
from datetime import timedelta
import os
import json

app = Flask(__name__)

# --- CONFIGURATION SÉCURITÉ ---
app.secret_key = "offranel_orange_secret"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# --- INITIALISATION FIREBASE ---
if not firebase_admin._apps:
    service_account_info = os.environ.get('FIREBASE_CONFIG')
    if service_account_info:
        cred = credentials.Certificate(json.loads(service_account_info))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


# --- ROUTES UTILISATEURS ---

@app.route('/')
def index():
    products_stream = db.collection('products').order_by('created_at', direction='DESCENDING').stream()
    products = []
    for doc in products_stream:
        p = doc.to_dict()
        p['id'] = doc.id
        products.append(p)
    return render_template('index.html', products=products)


@app.route('/profile')
@app.route('/profile/<uid>')
def profile(uid=None):
    target_uid = uid if uid else session.get('user_id')
    if not target_uid:
        return redirect(url_for('login_page'))

    user_doc = db.collection('users').document(target_uid).get()
    if user_doc.exists:
        return render_template('profile.html', user=user_doc.to_dict())
    return "Utilisateur non trouvé 👤", 404


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/set_session', methods=['POST'])
def set_session():
    data = request.get_json()
    uid = data.get('uid')
    session.permanent = True

    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()

    role = user_doc.to_dict().get('role', 'user') if user_doc.exists else 'user'

    if not user_doc.exists:
        user_ref.set({
            'name': data.get('name'),
            'email': data.get('email'),
            'photo': data.get('photo'),
            'role': role,
            'created_at': datetime.datetime.now()
        })

    session.update({'user_id': uid, 'name': data.get('name'), 'photo': data.get('photo'), 'role': role})
    return jsonify({"status": "ok", "role": role})


# --- ROUTES ADMINISTRATION ---

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect('/')

    # Calcul des statistiques
    users_list = list(db.collection('users').stream())
    products_list = list(db.collection('products').stream())

    stats = {
        "total_users": len(users_list),
        "total_products": len(products_list),
        "active_now": 1
    }
    return render_template('admin_dashboard.html', stats=stats)


@app.route('/publier', methods=['GET', 'POST'])
def publier():
    if session.get('role') != 'admin':
        return redirect('/')

    if request.method == 'POST':
        data = request.get_json()
        # On enregistre une LISTE de photos (photo_urls au pluriel)
        db.collection('products').add({
            'title': data.get('title'),
            'price': data.get('price'),
            'currency': data.get('currency'),
            'description': data.get('description'),
            'photo_urls': data.get('photo_urls'),  # Reçoit une liste de base64
            'created_at': datetime.datetime.now()
        })
        return jsonify({"status": "success"})
    return render_template('publier.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
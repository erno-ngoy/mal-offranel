from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
from datetime import timedelta
import os
import json

app = Flask(__name__)

# --- CONFIGURATION SÉCURITÉ ET SESSION ---
app.secret_key = "offranel_orange_secret"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# --- INITIALISATION FIREBASE ---
if not firebase_admin._apps:
    service_account_info = os.environ.get('FIREBASE_CONFIG')
    if service_account_info:
        cred_dict = json.loads(service_account_info)
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- ROUTES UTILISATEURS ---

@app.route('/')
def index():
    try:
        products_stream = db.collection('products').order_by('created_at', direction='DESCENDING').stream()
        products = []
        for doc in products_stream:
            p = doc.to_dict()
            p['id'] = doc.id
            products.append(p)
    except Exception as e:
        print(f"Erreur Firestore : {e}")
        products = []
    return render_template('index.html', products=products)

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

    if not user_doc.exists:
        role = 'user'
        user_ref.set({
            'name': data.get('name'),
            'email': data.get('email'),
            'photo': data.get('photo'),
            'role': role,
            'last_login': datetime.datetime.now()
        })
    else:
        role = user_doc.to_dict().get('role', 'user')
        user_ref.update({'last_login': datetime.datetime.now()})

    session.update({'user_id': uid, 'name': data.get('name'), 'photo': data.get('photo'), 'role': role})
    return jsonify({"status": "ok", "role": role})

@app.route('/produit/<id>')
def detail_produit(id):
    doc = db.collection('products').document(id).get()
    if doc.exists:
        return render_template('detail.html', product=doc.to_dict(), id=id)
    return "Produit non trouvé 😕", 404

# --- ROUTES ADMINISTRATEUR ---

@app.route('/publier', methods=['GET', 'POST'])
def publier():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            data = request.get_json()
            # On accepte la liste 'images' ou l'ancienne 'photo_url'
            images_list = data.get('images', [])
            if not images_list and data.get('photo_url'):
                images_list = [data.get('photo_url')]

            db.collection('products').add({
                'title': data.get('title'),
                'price': data.get('price'),
                'currency': data.get('currency'),
                'description': data.get('description'),
                'images': images_list,
                'created_at': datetime.datetime.now()
            })
            return jsonify({"status": "success"})
        except Exception as e:
            print(f"Erreur : {e}")
            return jsonify({"status": "error"}), 500

    return render_template('publier.html')

@app.route('/supprimer/<id>', methods=['POST'])
def supprimer(id):
    if session.get('role') == 'admin':
        db.collection('products').document(id).delete()
        flash("Produit supprimé", "success")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
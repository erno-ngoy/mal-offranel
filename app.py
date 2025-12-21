from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import os
import json

app = Flask(__name__)
app.secret_key = "offranel_orange_secret"

# --- INITIALISATION FIREBASE ( Railway + Local ) ---
if not firebase_admin._apps:
    # On cherche d'abord la variable d'environnement (pour Railway)
    service_account_info = os.environ.get('FIREBASE_CONFIG')

    if service_account_info:
        # Configuration pour Railway
        cred_dict = json.loads(service_account_info)
        cred = credentials.Certificate(cred_dict)
    else:
        # Configuration pour ton PC local
        # Assure-toi que le fichier est bien présent dans ton dossier
        cred = credentials.Certificate("serviceAccountKey.json")

    firebase_admin.initialize_app(cred)

db = firestore.client()


# --- ROUTES PRINCIPALES ---

@app.route('/')
def index():
    products_stream = db.collection('products').order_by('created_at', direction='DESCENDING').stream()
    products = []
    for doc in products_stream:
        p = doc.to_dict()
        p['id'] = doc.id
        products.append(p)
    return render_template('index.html', products=products)


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/set_session', methods=['POST'])
def set_session():
    data = request.get_json()
    uid = data.get('uid')
    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()

    if not user_doc.exists:
        role = 'user'
        user_ref.set({
            'name': data.get('name'),
            'email': data.get('email'),
            'photo': data.get('photo'),
            'role': role
        })
    else:
        role = user_doc.to_dict().get('role', 'user')

    session.update({
        'user_id': uid,
        'name': data.get('name'),
        'photo': data.get('photo'),
        'role': role
    })
    return jsonify({"status": "ok", "role": role})


@app.route('/profile')
@app.route('/profile/<uid>')
def profile(uid=None):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('profile.html')


@app.route('/publier', methods=['GET', 'POST'])
def publier():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.get_json()
        db.collection('products').add({
            'title': data.get('title'),
            'price': data.get('price'),
            'currency': data.get('currency'),
            'description': data.get('description'),
            'images': [data.get('photo_url')],
            'created_at': datetime.datetime.now()
        })
        return jsonify({"status": "success"})

    return render_template('publier.html')


@app.route('/produit/<id>')
def detail_produit(id):
    doc = db.collection('products').document(id).get()
    if doc.exists:
        return render_template('detail.html', product=doc.to_dict(), id=id)
    return "Produit non trouvé 😕", 404


@app.route('/supprimer/<id>', methods=['POST'])
def supprimer(id):
    if session.get('role') == 'admin':
        db.collection('products').document(id).delete()
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
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
# Garde l'utilisateur connecté pendant 30 jours (indispensable pour mobile)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# --- INITIALISATION FIREBASE (RAILWAY + LOCAL) ---
if not firebase_admin._apps:
    service_account_info = os.environ.get('FIREBASE_CONFIG')
    if service_account_info:
        # Configuration Railway (Variable d'environnement)
        cred_dict = json.loads(service_account_info)
        cred = credentials.Certificate(cred_dict)
    else:
        # Configuration Local (Fichier JSON)
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


# --- ROUTES UTILISATEURS ---

@app.route('/')
def index():
    try:
        # Récupération des articles triés par date (les plus récents en premier)
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

    # Activation de la session longue durée
    session.permanent = True

    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()

    # Déterminer le rôle (Admin ou User)
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

    session.update({
        'user_id': uid,
        'name': data.get('name'),
        'photo': data.get('photo'),
        'role': role
    })
    return jsonify({"status": "ok", "role": role})


@app.route('/produit/<id>')
def detail_produit(id):
    doc = db.collection('products').document(id).get()
    if doc.exists:
        return render_template('detail.html', product=doc.to_dict(), id=id)
    return "Produit non trouvé 😕", 404


@app.route('/panier')
def panier():
    return render_template('panier.html')


@app.route('/a-propos')
def a_propos():
    return render_template('a_propos.html')


# --- ROUTES ADMINISTRATEUR (SÉCURISÉES) ---

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    # Statistiques pour le graphique et les cartes
    users_count = len(list(db.collection('users').stream()))
    products_count = len(list(db.collection('products').stream()))

    stats = {
        "total_users": users_count,
        "total_products": products_count,
        "active_now": 1  # Simulation d'activité
    }
    return render_template('admin_dashboard.html', stats=stats)


@app.route('/publier', methods=['GET', 'POST'])
def publier():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            data = request.get_json()

            # --- MODIFICATION ICI ---
            # On récupère soit la liste 'images', soit 'photo_url' transformé en liste
            images_list = data.get('images', [])
            if not images_list and data.get('photo_url'):
                images_list = [data.get('photo_url')]

            # Sécurité : Si toujours rien, on évite d'enregistrer du vide
            if not images_list:
                return jsonify({"status": "error", "message": "Aucune image reçue"}), 400

            db.collection('products').add({
                'title': data.get('title'),
                'price': data.get('price'),
                'currency': data.get('currency'),
                'description': data.get('description'),
                'images': images_list,  # Stocké en tant que liste
                'created_at': datetime.datetime.now()
            })
            return jsonify({"status": "success"})
        except Exception as e:
            print(f"Erreur lors de la publication : {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    return render_template('publier.html')


@app.route('/api/publier_multiple', methods=['POST'])
def api_publier_multiple():
    if session.get('role') != 'admin':
        return jsonify({"status": "error"}), 403

    data = request.get_json()
    produits = data.get('produits', [])
    batch = db.batch()

    for p in produits:
        doc_ref = db.collection('products').document()
        p['created_at'] = datetime.datetime.now()
        batch.set(doc_ref, p)

    batch.commit()
    return jsonify({"status": "success"})


@app.route('/supprimer/<id>', methods=['POST'])
def supprimer(id):
    if session.get('role') == 'admin':
        db.collection('products').document(id).delete()
        flash("Produit supprimé avec succès", "success")
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# --- LANCEMENT SERVEUR ---
if __name__ == '__main__':
    # Indispensable pour Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
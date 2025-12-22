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


@app.route('/profile')
@app.route('/profile/<uid>')
def profile(uid=None):
    target_uid = uid if uid else session.get('user_id')
    if not target_uid:
        return redirect(url_for('login_page'))
    user_doc = db.collection('users').document(target_uid).get()
    if user_doc.exists:
        return render_template('profile.html', user=user_doc.to_dict())
    return "Utilisateur non trouvé 😕", 404


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


@app.route('/panier')
def panier():
    return render_template('panier.html')


@app.route('/a-propos')
def a_propos():
    about_doc = db.collection('settings').document('about_us').get()
    content = about_doc.to_dict() if about_doc.exists else {"text": "Bienvenue sur Offranel Shop !"}
    return render_template('a_propos.html', content=content)


# API pour que le JavaScript récupère le message du pop-up
@app.route('/api/get_popup')
def get_popup():
    doc = db.collection('settings').document('popup_message').get()
    if doc.exists:
        return jsonify(doc.to_dict())
    return jsonify({"active": False})


# --- ROUTES ADMINISTRATEUR ---

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    users_count = len(list(db.collection('users').stream()))
    products_count = len(list(db.collection('products').stream()))

    # Récupération de la config actuelle du popup
    pop_doc = db.collection('settings').document('popup_message').get()
    popup_data = pop_doc.to_dict() if pop_doc.exists else {"title": "", "content": "", "active": False}

    stats = {"total_users": users_count, "total_products": products_count, "active_now": 1}
    return render_template('admin_dashboard.html', stats=stats, popup=popup_data)


@app.route('/admin/update_popup', methods=['POST'])
def update_popup():
    if session.get('role') != 'admin':
        return jsonify({"status": "error"}), 403
    data = request.get_json()
    db.collection('settings').document('popup_message').set({
        'title': data.get('title'),
        'content': data.get('content'),
        'active': data.get('active'),
        'updated_at': datetime.datetime.now()
    })
    return jsonify({"status": "success"})


@app.route('/admin/modifier-a-propos', methods=['GET', 'POST'])
def edit_about():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    if request.method == 'POST':
        new_text = request.form.get('about_text')
        db.collection('settings').document('about_us').set({"text": new_text})
        flash("Page 'À propos' mise à jour !", "success")
        return redirect(url_for('a_propos'))
    about_doc = db.collection('settings').document('about_us').get()
    current_text = about_doc.to_dict().get('text', '') if about_doc.exists else ""
    return render_template('edit_about.html', current_text=current_text)


@app.route('/publier', methods=['GET', 'POST'])
def publier():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
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
        except Exception as e:
            print(f"ERREUR LORS DE LA PUBLICATION : {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    return render_template('publier.html')


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


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
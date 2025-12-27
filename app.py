from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
from datetime import timedelta
import os
import json
from functools import wraps
from pywebpush import webpush, WebPushException

app = Flask(__name__)

# --- CONFIGURATION SÉCURITÉ ET SESSION ---
app.secret_key = "offranel_orange_secret"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# --- CONFIGURATION NOTIFICATIONS PUSH (VAPID) ---
VAPID_PUBLIC_KEY = "BOT0JEWz9-w_eTSqZXlLXewXXq4hT3zvWPFfyb68z-aH80OVc1oX2xvftH4d3rhQMKT5ibT8vkHK7vAIbaTq29Q"
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "VOTRE_CLE_PRIVEE_SECRET")
VAPID_CLAIMS = {"sub": "mailto:admin@offranel.com"}

# --- LISTE DES CATÉGORIES (MISES À JOUR) ---
CATEGORIES = [
    "👗 Mode & Vêtements",
    "📱 Accessoires Téléphones",
    "🎧 Gadgets & Audio",
    "📦 Autres"
]

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


# --- DÉCORATEUR DE SÉCURITÉ ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Veuillez vous connecter pour effectuer cette action 🔐", "warning")
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)

    return decorated_function


# --- FONCTION D'ENVOI D'ALERTES PUSH ---
def trigger_push_notifications(title, body):
    try:
        subscriptions = db.collection('push_subscriptions').stream()
        for sub in subscriptions:
            try:
                sub_data = sub.to_dict()
                webpush(
                    subscription_info=sub_data,
                    data=json.dumps({"title": title, "body": body, "icon": "/static/img/image.png"}),
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
            except WebPushException as ex:
                if ex.response and ex.response.status_code in [404, 410]:
                    db.collection('push_subscriptions').document(sub.id).delete()
    except Exception as e:
        print(f"Erreur globale Push: {e}")


# --- ROUTES UTILISATEURS ---

@app.route('/')
def index():
    search_query = request.args.get('search', '').lower()
    category_filter = request.args.get('category', '')

    popup_data = None
    try:
        pop_doc = db.collection('settings').document('popup_message').get()
        if pop_doc.exists:
            popup_data = pop_doc.to_dict()
    except Exception as e:
        print(f"Erreur popup index: {e}")

    try:
        # Optimisation : on filtre par catégorie directement via Firestore si possible
        products_ref = db.collection('products').order_by('created_at', direction='DESCENDING')

        if category_filter:
            products_ref = products_ref.where('category', '==', category_filter)

        products_stream = products_ref.stream()
        products = []
        for doc in products_stream:
            p = doc.to_dict()
            p['id'] = doc.id
            match_search = search_query in p.get('title', '').lower() if search_query else True
            if match_search:
                products.append(p)
    except Exception as e:
        print(f"Erreur Firestore : {e}")
        products = []

    return render_template('index.html', products=products, categories=CATEGORIES, popup=popup_data)


@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/api/save-subscription', methods=['POST'])
def save_subscription():
    data = request.get_json()
    if data:
        sub_id = session.get('user_id', f"guest_{datetime.datetime.now().timestamp()}")
        db.collection('push_subscriptions').document(str(sub_id)).set(data)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400


@app.route('/profile')
@app.route('/profile/<uid>')
@login_required
def profile(uid=None):
    target_uid = uid if uid and uid != 'None' else session.get('user_id')
    try:
        user_doc = db.collection('users').document(target_uid).get()
        if user_doc.exists:
            user_info = user_doc.to_dict()
            user_info['id'] = user_doc.id
            user_products = []
            try:
                products_ref = db.collection('products').where('author_id', '==', target_uid).order_by('created_at',
                                                                                                       direction='DESCENDING').stream()
                for doc in products_ref:
                    p = doc.to_dict()
                    p['id'] = doc.id
                    user_products.append(p)
            except Exception:
                products_ref = db.collection('products').where('author_id', '==', target_uid).stream()
                for doc in products_ref:
                    p = doc.to_dict()
                    p['id'] = doc.id
                    user_products.append(p)
            return render_template('profile.html', user=user_info, products=user_products)
        flash("Profil introuvable.", "danger")
        return redirect(url_for('index'))
    except Exception:
        return "Erreur Interne du Serveur", 500


@app.route('/set_session', methods=['POST'])
def set_session():
    data = request.get_json()
    uid = data.get('uid')
    user_name = data.get('name', 'Utilisateur')
    session.permanent = True
    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()

    if not user_doc.exists:
        role = 'user'
        user_ref.set({
            'name': user_name, 'email': data.get('email'), 'photo': data.get('photo'),
            'role': role, 'last_login': datetime.datetime.now(),
            'points': 0  # Initialisation des points de parrainage
        })
    else:
        role = user_doc.to_dict().get('role', 'user')
        user_name = user_doc.to_dict().get('name', user_name)
        user_ref.update({'last_login': datetime.datetime.now()})

    session.update({'user_id': uid, 'name': user_name, 'photo': data.get('photo'), 'role': role})
    return jsonify({"status": "ok", "role": role, "username": user_name})


@app.route('/produit/<id>')
@login_required
def detail_produit(id):
    doc = db.collection('products').document(id).get()
    if doc.exists:
        return render_template('detail.html', product=doc.to_dict(), id=id)
    return "Produit non trouvé 😕", 404


@app.route('/panier')
@login_required
def panier():
    return render_template('panier.html')


@app.route('/a-propos')
def a_propos():
    try:
        about_doc = db.collection('settings').document('about_us').get()
        content = about_doc.to_dict() if about_doc.exists else {"text": "Bienvenue sur Offranel Shop !"}
        return render_template('a_propos.html', content=content)
    except Exception:
        return render_template('a_propos.html', content={"text": "Bienvenue sur Offranel Shop !"})


@app.route('/parrainage')
@login_required
def parrainage():
    uid = session.get('user_id')
    user_doc = db.collection('users').document(uid).get()
    user_data = user_doc.to_dict() if user_doc.exists else {"points": 0}
    # Lien de parrainage basé sur l'UID
    referral_link = f"{request.host_url}login?ref={uid}"
    return render_template('parrainage.html', points=user_data.get('points', 0), ref_link=referral_link)


@app.route('/api/get_popup')
def get_popup():
    doc = db.collection('settings').document('popup_message').get()
    if doc.exists:
        return jsonify(doc.to_dict())
    return jsonify({"active": False})


@app.route('/api/get_last_notif')
def get_last_notif():
    notif_ref = db.collection('notifications').order_by('timestamp', direction='DESCENDING').limit(1).get()
    if notif_ref:
        return jsonify(notif_ref[0].to_dict())
    return jsonify({"id": None})


# --- ROUTES ADMINISTRATEUR ---

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    users_count = len(list(db.collection('users').stream()))
    products_count = len(list(db.collection('products').stream()))
    pop_doc = db.collection('settings').document('popup_message').get()
    popup_data = pop_doc.to_dict() if pop_doc.exists else {"title": "", "content": "", "active": False}
    stats = {"total_users": users_count, "total_products": products_count, "active_now": 1}
    return render_template('admin_dashboard.html', stats=stats, popup=popup_data)


@app.route('/admin/toggle_stock/<id>', methods=['POST'])
@login_required
def toggle_stock(id):
    if session.get('role') != 'admin':
        return jsonify({"status": "error"}), 403
    product_ref = db.collection('products').document(id)
    doc = product_ref.get()
    if doc.exists:
        current_status = doc.to_dict().get('in_stock', True)
        product_ref.update({'in_stock': not current_status})
        return jsonify({"status": "success", "new_status": not current_status})
    return jsonify({"status": "error"}), 404


@app.route('/admin/update_popup', methods=['POST'])
@login_required
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
@login_required
def edit_about():
    if session.get('role') != 'admin':
        flash("Accès refusé. Réservé aux administrateurs.", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            new_text = request.form.get('about_text')
            db.collection('settings').document('about_us').set({"text": new_text})
            flash("Page 'À propos' mise à jour avec succès !", "success")
            return redirect(url_for('a_propos'))
        except Exception:
            flash("Erreur lors de la sauvegarde.", "danger")
            return redirect(url_for('index'))
    about_doc = db.collection('settings').document('about_us').get()
    current_text = about_doc.to_dict().get('text', '') if about_doc.exists else ""
    return render_template('edit_about.html', current_text=current_text)


@app.route('/publier', methods=['GET', 'POST'])
@login_required
def publier():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            data = request.get_json()
            new_product_ref = db.collection('products').add({
                'title': data.get('title'),
                'price': data.get('price'),
                'currency': data.get('currency'),
                'category': data.get('category'),
                'description': data.get('description'),
                'images': data.get('images'),
                'in_stock': True,
                'author_id': session.get('user_id'),
                'author_name': session.get('name'),
                'author_photo': session.get('photo'),
                'is_admin_post': True,
                'created_at': datetime.datetime.now()
            })
            db.collection('notifications').add({
                'id': str(datetime.datetime.now().timestamp()),
                'title': "Nouvel arrivage ! 🍊",
                'message': f"{data.get('title')} est maintenant disponible.",
                'timestamp': datetime.datetime.now()
            })
            trigger_push_notifications("OFFRANEL : Nouveau produit ! 🍊", f"Découvrez : {data.get('title')}")
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return render_template('publier.html', categories=CATEGORIES)


@app.route('/supprimer/<id>', methods=['POST'])
@login_required
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
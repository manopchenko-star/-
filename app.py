import os
import json
from flask import Flask, redirect, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = "super_secret_school_key_123"
DB_FILE = 'database.json'

def load_db():
    if not os.path.exists(DB_FILE):
        default_db = {
            "admins": [{"login": "Maksim", "name": "Максим", "password": "Anopchenko2011", "perms": {"canGdz": True, "canEditGdz": True, "canUsers": True}}],
            "ideas": [], "gdz": [], "participants": {}, "broadcasts": [], "admin_logs": [],
            "settings": {"redirectAll": False}
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_db, f, ensure_ascii=False, indent=2)
        return default_db
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            db = json.load(f)
            if "settings" not in db: db["settings"] = {"redirectAll": False}
            return db
    except:
        return {"admins": [], "ideas": [], "gdz": [], "participants": {}, "broadcasts": [], "admin_logs": [], "settings": {"redirectAll": False}}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.before_request
def check_redirect():
    if request.path.startswith('/api/'):
        return

    db = load_db()
    settings = db.get("settings", {})
    
    if settings.get('redirectAll'):
        if session.get('admin_login') != 'Maksim':
            return redirect("http://de-bots5.h1cloud.net:25191/")

@app.route('/')
def index():
    return render_template('student.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    db = load_db()
    return jsonify({
        "ideas": db.get("ideas", []), 
        "gdz": db.get("gdz", []),
        "admins": [{"login": a["login"], "name": a.get("name", ""), "perms": a.get("perms")} for a in db.get("admins", [])],
        "participants": db.get("participants", {}), 
        "broadcasts": db.get("broadcasts", []), 
        "adminLogs": db.get("admin_logs", []),
        "currentAdmin": session.get('admin_login'), 
        "settings": db.get("settings", {})
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    db = load_db()
    for a in db["admins"]:
        if a["login"] == data["login"] and a.get("password") == data["password"]:
            session['admin_login'] = a["login"]
            save_db(db)
            return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Неверный логин или пароль"})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('admin_login', None)
    return jsonify({"status": "ok"})

@app.route('/api/admin/action', methods=['POST'])
def admin_action():
    if not session.get('admin_login'): 
        return jsonify({"status": "error", "message": "Нет доступа"})
    
    data = request.json
    action = data.get("action")
    db = load_db()
    
    if action == "save_settings":
        db["settings"] = data["settings"]
    elif action == "add_admin":
        if not any(a["login"] == data["login"] for a in db["admins"]):
            db["admins"].append({"login": data["login"], "name": data.get("name", ""), "password": data["password"], "perms": {"canGdz": True, "canEditGdz": True, "canUsers": True}})
    elif action == "del_admin":
        db["admins"] = [a for a in db["admins"] if a["login"] != data["login"]]
                
    save_db(db)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)

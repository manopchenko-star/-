import os
import json
import uuid
import urllib3
import requests
import time
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_fallback_key")
SBER_AUTH_KEY = os.getenv("SBER_AUTH_KEY")

DB_FILE = 'database.json'

def load_db():
    if not os.path.exists(DB_FILE):
        default_db = {
            "admins": [
                {"login": "Maksim", "name": "Максим", "password": generate_password_hash("Anopchenko2011"), "perms": {"canGdz": True, "canEditGdz": True, "canUsers": True}}
            ],
            "ideas": [],
            "gdz": [],
            "settings": {
                "ideasEnabled": True, "gdzEnabled": True, "photoEnabled": True,
                "showIdeasList": True, "requireName": False, "maxText": 1200,
                "botTitle": "Нейро-ГДЗ", "notice": ""
            }
        }
        save_db(default_db)
        return default_db
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            db = json.load(f)
            if "settings" not in db:
                db["settings"] = {"ideasEnabled": True, "gdzEnabled": True, "photoEnabled": True, "showIdeasList": True, "requireName": False, "maxText": 1200, "botTitle": "Нейро-ГДЗ", "notice": ""}
            return db
    except:
        return {"admins": [], "ideas": [], "gdz": [], "settings": {}}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ask_gigachat(question):
    if not SBER_AUTH_KEY:
        return "Ошибка конфигурации сервера."
    try:
        auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
            'Authorization': f'Basic {SBER_AUTH_KEY}'
        }
        payload = "scope=GIGACHAT_API_PERS"
        
        auth_res = requests.post(auth_url, headers=headers, data=payload, verify=False)
        token = auth_res.json().get('access_token')
        
        chat_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        chat_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        system_prompt = f"ВОПРОС: {question}\nРеши задачу по шагам. Проверь решение 10 раз. Выдай только финальный ответ."
        
        chat_payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": system_prompt}],
            "temperature": 0.1
        }
        
        chat_res = requests.post(chat_url, headers=chat_headers, json=chat_payload, verify=False)
        return chat_res.json()['choices'][0]['message']['content']
    except Exception:
        return "Не удалось связаться с нейросетью. Попробуйте позже."

@app.route('/')
def index():
    return render_template('student.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    db = load_db()
    current_admin = session.get('admin_login')
    return jsonify({
        "ideas": db["ideas"],
        "gdz": db["gdz"],
        "admins": [{"login": a["login"], "name": a.get("name", ""), "perms": a.get("perms")} for a in db["admins"]],
        "currentAdmin": current_admin,
        "settings": db.get("settings", {})
    })

@app.route('/api/idea', methods=['POST'])
def add_idea():
    data = request.json
    db = load_db()
    db["ideas"].insert(0, {
        "id": str(uuid.uuid4()),
        "text": data.get("text"),
        "author": data.get("author", "Аноним"),
        "status": "pending",
        "comment": "",
        "createdAt": int(time.time() * 1000)
    })
    save_db(db)
    return jsonify({"status": "ok"})

@app.route('/api/gdz', methods=['POST'])
def add_gdz():
    data = request.json
    db = load_db()
    question = data.get("question")
    bot_answer = ask_gigachat(question)
    
    rec = {
        "id": str(uuid.uuid4()),
        "question": question,
        "author": data.get("author", "Аноним"),
        "botAnswer": bot_answer,
        "adminAnswer": "",
        "status": "new",
        "createdAt": int(time.time() * 1000)
    }
    db["gdz"].insert(0, rec)
    save_db(db)
    return jsonify({"status": "ok", "answer": bot_answer})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    db = load_db()
    for a in db["admins"]:
        if a["login"] == data["login"] and check_password_hash(a["password"], data["password"]):
            session['admin_login'] = a["login"]
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
    
    if action == "save_idea":
        for i in db["ideas"]:
            if i["id"] == data["id"]:
                i["status"] = data["status"]
                i["comment"] = data["comment"]
                break
    elif action == "del_idea":
        db["ideas"] = [i for i in db["ideas"] if i["id"] != data["id"]]
    elif action == "save_gdz":
        for g in db["gdz"]:
            if g["id"] == data["id"]:
                g["status"] = data["status"]
                g["adminAnswer"] = data["adminAnswer"]
                break
    elif action == "del_gdz":
        db["gdz"] = [g for g in db["gdz"] if g["id"] != data["id"]]
    elif action == "add_admin":
        if not any(a["login"] == data["login"] for a in db["admins"]):
            db["admins"].append({
                "login": data["login"],
                "name": data.get("name", ""),
                "password": generate_password_hash(data["password"]),
                "perms": {"canGdz": True, "canEditGdz": True, "canUsers": True}
            })
    elif action == "del_admin":
        db["admins"] = [a for a in db["admins"] if a["login"] != data["login"]]
    elif action == "update_perms":
        for a in db["admins"]:
            if a["login"] == data["login"]:
                a["perms"][data["perm"]] = data["value"]
                break
    elif action == "save_settings":
        db["settings"] = data["settings"]
                
    save_db(db)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

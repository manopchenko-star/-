import os
import json
import uuid
import requests
import time
import threading
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "super_secret_school_key_123"

ODIROUTER_API_KEY = "sk-anSU8jie84b47FPQtE3yh4iCDnqWTfQmfROfX1iOJVzmIMzV"
DB_FILE = 'database.json'
db_lock = threading.RLock()

def load_db():
    with db_lock:
        if not os.path.exists(DB_FILE):
            default_db = {
                "admins": [{"login": "Maksim", "name": "Максим", "password": generate_password_hash("Anopchenko2011"), "perms": {"canGdz": True, "canEditGdz": True, "canUsers": True}}],
                "ideas": [], "gdz": [], "participants": {}, "broadcasts": [], "admin_logs": [],
                "settings": {"ideasEnabled": True, "gdzEnabled": True, "photoEnabled": True, "showIdeasList": True, "requireName": True, "maxText": 1200, "botTitle": "Нейро-ГДЗ", "notice": "", "maintenanceMode": False, "maintenanceText": "Сайт на техобслуживании, скоро вернемся!"}
            }
            save_db(default_db)
            return default_db
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                db = json.load(f)
                if "settings" not in db: 
                    db["settings"] = {"ideasEnabled": True, "gdzEnabled": True, "photoEnabled": True, "showIdeasList": True, "requireName": True, "maxText": 1200, "botTitle": "Нейро-ГДЗ", "notice": "", "maintenanceMode": False, "maintenanceText": "Сайт на техобслуживании, скоро вернемся!"}
                if "participants" not in db: db["participants"] = {}
                if "broadcasts" not in db: db["broadcasts"] = []
                if "admin_logs" not in db: db["admin_logs"] = []
                return db
        except Exception as e:
            print("DB ERROR:", e)
            return {"admins": [], "ideas": [], "gdz": [], "participants": {}, "broadcasts": [], "admin_logs": [], "settings": {}}

def save_db(data):
    with db_lock:
        temp_file = DB_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, DB_FILE)

def add_log(db, admin, action):
    db["admin_logs"].insert(0, {"time": int(time.time() * 1000), "admin": admin, "action": action})
    if len(db["admin_logs"]) > 200: 
        db["admin_logs"] = db["admin_logs"][:200]

def add_participant(db, author):
    if author and author != "Аноним" and author not in db["participants"]:
        db["participants"][author] = {"role": "student"}

def ask_ai(question, image_data=None):
    try:
        url = "https://api.odirouter.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {ODIROUTER_API_KEY}", "Content-Type": "application/json"}
        prompt_text = f"Ты — умный школьный ИИ-помощник. Общайся дружелюбно. Если просят решить задачу, реши её по шагам и выдай финальный ответ.\n\nЗапрос: {question}"
        
        if image_data:
            content = [{"type": "text", "text": prompt_text}, {"type": "image_url", "image_url": {"url": image_data}}]
        else:
            content = prompt_text

        payload = {"model": "free-gemini-3.1-flash-lite", "messages": [{"role": "user", "content": content}], "temperature": 0.3}
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200: 
            return response.json()['choices'][0]['message']['content']
        else: 
            return f"Ошибка API ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Системная ошибка: {str(e)}"

def process_ai_response(rec_id, question, image):
    answer = ask_ai(question, image)
    db = load_db()
    for r in db["gdz"]:
        if r["id"] == rec_id:
            r["botAnswer"] = answer
            break
    save_db(db)

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
        "ideas": db["ideas"], "gdz": db["gdz"],
        "admins": [{"login": a["login"], "name": a.get("name", ""), "perms": a.get("perms")} for a in db["admins"]],
        "participants": db.get("participants", {}), "broadcasts": db.get("broadcasts", []), "adminLogs": db.get("admin_logs", []),
        "currentAdmin": session.get('admin_login'), "settings": db.get("settings", {})
    })

@app.route('/api/idea', methods=['POST'])
def add_idea():
    data = request.json
    db = load_db()
    author = data.get("author", "Аноним")
    add_participant(db, author)
    db["ideas"].insert(0, {"id": str(uuid.uuid4()), "text": data.get("text"), "author": author, "image": data.get("image", ""), "adminNote": "", "likes": [], "dislikes": [], "status": "pending", "comment": "", "createdAt": int(time.time() * 1000)})
    save_db(db)
    return jsonify({"status": "ok"})

@app.route('/api/idea/vote', methods=['POST'])
def vote_idea():
    data = request.json
    idea_id = data.get("id")
    author = data.get("author")
    vote_type = data.get("type")
    if not author or author == "Аноним": 
        return jsonify({"status": "error", "message": "Укажите имя"})
    db = load_db()
    for i in db["ideas"]:
        if i["id"] == idea_id:
            if "likes" not in i: i["likes"] = []
            if "dislikes" not in i: i["dislikes"] = []
            if vote_type == "like":
                if author in i["likes"]: 
                    i["likes"].remove(author)
                else: 
                    i["likes"].append(author)
                    i["dislikes"] = [x for x in i["dislikes"] if x != author]
            elif vote_type == "dislike":
                if author in i["dislikes"]: 
                    i["dislikes"].remove(author)
                else: 
                    i["dislikes"].append(author)
                    i["likes"] = [x for x in i["likes"] if x != author]
            break
    save_db(db)
    return jsonify({"status": "ok"})

@app.route('/api/gdz', methods=['POST'])
def add_gdz():
    data = request.json
    db = load_db()
    question = data.get("question", "")
    author = data.get("author", "Аноним")
    image = data.get("image", "")
    add_participant(db, author)
    rec_id = str(uuid.uuid4())
    db["gdz"].insert(0, {"id": rec_id, "question": question, "author": author, "image": image, "botAnswer": "Думаю...", "adminAnswer": "", "status": "new", "createdAt": int(time.time() * 1000)})
    save_db(db)
    threading.Thread(target=process_ai_response, args=(rec_id, question, image)).start()
    return jsonify({"status": "ok"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    db = load_db()
    for a in db["admins"]:
        if a["login"] == data["login"] and check_password_hash(a["password"], data["password"]):
            session['admin_login'] = a["login"]
            add_log(db, a["login"], "Вход в систему")
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
    current_admin = session.get('admin_login')
    
    if action == "save_idea":
        for i in db["ideas"]:
            if i["id"] == data["id"]:
                i["status"] = data["status"]
                i["comment"] = data["comment"]
                if "adminNote" in data: i["adminNote"] = data["adminNote"]
                break
        add_log(db, current_admin, "Обновил идею")
    elif action == "del_idea":
        db["ideas"] = [i for i in db["ideas"] if i["id"] != data["id"]]
        add_log(db, current_admin, "Удалил идею")
    elif action == "bulk_delete":
        db["ideas"] = [i for i in db["ideas"] if i["id"] not in data.get("ids", [])]
        add_log(db, current_admin, f"Массово удалил {len(data.get('ids', []))} идей")
    elif action == "bulk_approve":
        for i in db["ideas"]:
            if i["id"] in data.get("ids", []): i["status"] = "approved"
        add_log(db, current_admin, f"Массово принял {len(data.get('ids', []))} идей")
    elif action == "save_gdz":
        for g in db["gdz"]:
            if g["id"] == data["id"]: 
                g["status"] = data["status"]
                g["adminAnswer"] = data["adminAnswer"]
                break
        add_log(db, current_admin, "Ответил на ГДЗ")
    elif action == "del_gdz":
        db["gdz"] = [g for g in db["gdz"] if g["id"] != data["id"]]
        add_log(db, current_admin, "Удалил запрос ГДЗ")
    elif action == "add_admin":
        if not any(a["login"] == data["login"] for a in db["admins"]):
            db["admins"].append({"login": data["login"], "name": data.get("name", ""), "password": generate_password_hash(data["password"]), "perms": {"canGdz": True, "canEditGdz": True, "canUsers": True}})
            add_log(db, current_admin, f"Создал админа {data['login']}")
    elif action == "del_admin":
        db["admins"] = [a for a in db["admins"] if a["login"] != data["login"]]
        add_log(db, current_admin, f"Удалил админа {data['login']}")
    elif action == "update_perms":
        for a in db["admins"]:
            if a["login"] == data["login"]: 
                a["perms"][data["perm"]] = data["value"]
                break
        add_log(db, current_admin, f"Изменил права {data['login']}")
    elif action == "save_settings":
        db["settings"] = data["settings"]
        add_log(db, current_admin, "Изменил настройки")
    elif action == "set_role":
        if data.get("name"):
            if data["name"] not in db["participants"]: db["participants"][data["name"]] = {}
            db["participants"][data["name"]]["role"] = data.get("role")
            add_log(db, current_admin, f"Выдал роль {data.get('role')}")
    elif action == "add_broadcast":
        db["broadcasts"].insert(0, {"id": str(uuid.uuid4()), "text": data["text"], "createdAt": int(time.time() * 1000)})
        add_log(db, current_admin, "Отправил рассылку")
    elif action == "del_broadcast":
        db["broadcasts"] = [b for b in db["broadcasts"] if b["id"] != data["id"]]
        add_log(db, current_admin, "Удалил рассылку")
                
    save_db(db)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 25191))
    app.run(host='0.0.0.0', port=port, threaded=True)

import os
import json
import time
import urllib.request
import urllib.parse

# ================= НАСТРОЙКИ =================
TOKEN = "8590102450:AAHA7TkVnZNJvTsKYFRmu6trO879KGgOEVs"
SECRET_CODE = "vpiМяумура лучший 1488"
API_URL = f"https://api.telegram.org/bot{TOKEN}/"

# Пути для файлов (Render предоставляет временный диск)
PLAYERS_FILE = "/tmp/players.json"
ARTICLES_FILE = "/tmp/articles.txt"
OFFSET_FILE = "/tmp/offset.txt"

# ================= ЛОГИКА (БЕЗ ИЗМЕНЕНИЙ) =================
def load_players():
    if os.path.exists(PLAYERS_FILE):
        with open(PLAYERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_players(players):
    with open(PLAYERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(players, f, ensure_ascii=False, indent=2)

def update_article_file(country, text):
    separator = "-----------\n"
    if not os.path.exists(ARTICLES_FILE):
        with open(ARTICLES_FILE, 'w', encoding='utf-8') as f:
            f.write(f"{country}:\n{text}\n{separator}")
        return
    with open(ARTICLES_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    country_header = f"{country}:\n"
    country_index = -1
    for i, line in enumerate(lines):
        if line == country_header:
            country_index = i
            break
    if country_index != -1:
        separator_index = -1
        for i in range(country_index + 1, len(lines)):
            if lines[i] == separator:
                separator_index = i
                break
        if separator_index != -1:
            lines.insert(separator_index, f"{text}\n")
        else:
            lines.append(f"{text}\n{separator}")
        with open(ARTICLES_FILE, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    else:
        with open(ARTICLES_FILE, 'a', encoding='utf-8') as f:
            if lines and not lines[-1].endswith('\n'):
                f.write("\n")
            f.write(f"{country}:\n{text}\n{separator}")

def send_message(chat_id, text):
    url = API_URL + "sendMessage"
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': text}).encode('utf-8')
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data))
    except Exception:
        pass

def send_document(chat_id, file_path):
    url = API_URL + "sendDocument"
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    with open(file_path, 'rb') as f:
        file_content = f.read()
    body = [
        f'--{boundary}'.encode(), b'\r\n',
        f'Content-Disposition: form-data; name="chat_id"'.encode(), b'\r\n\r\n',
        str(chat_id).encode(), b'\r\n',
        f'--{boundary}'.encode(), b'\r\n',
        f'Content-Disposition: form-data; name="document"; filename="articles.txt"'.encode(), b'\r\n',
        f'Content-Type: text/plain'.encode(), b'\r\n\r\n',
        file_content, b'\r\n',
        f'--{boundary}--'.encode()
    ]
    body_bytes = b''.join(body)
    req = urllib.request.Request(url, data=body_bytes)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    try:
        urllib.request.urlopen(req)
    except Exception:
        pass

def process_message(message):
    chat_id = message.get('chat', {}).get('id')
    user_id = str(message.get('from', {}).get('id'))
    text = message.get('text', '').strip()
    if not text: return
    players = load_players()
    
    if text == '/start' or text == '/help':
        send_message(chat_id, "🤖 Бот ВПИ. Используйте /set_country НАЗВАНИЕ")
    elif text.startswith('/set_country'):
        parts = text.split(' ', 1)
        if len(parts) < 2:
            send_message(chat_id, "❌ /set_country НАЗВАНИЕ")
        else:
            country = parts[1].strip()
            players[user_id] = country
            save_players(players)
            send_message(chat_id, f"✅ Страна: {country}")
    elif text == '/my_country':
        if user_id in players:
            send_message(chat_id, f"🇺🇳 Ваша страна: {players[user_id]}")
        else:
            send_message(chat_id, "❌ Не установлена. /set_country")
    elif text == '/list':
        if not players:
            send_message(chat_id, "📭 Пусто.")
        else:
            msg = "👥 Игроки:\n" + "\n".join([f"• {c}" for c in players.values()])
            send_message(chat_id, msg)
    elif text.startswith('/get_file'):
        parts = text.split(' ')
        if len(parts) < 2 or parts[1] != SECRET_CODE:
            send_message(chat_id, "❌ Неверный код.")
        elif os.path.exists(ARTICLES_FILE):
            send_document(chat_id, ARTICLES_FILE)
        else:
            send_message(chat_id, "📄 Пусто.")
    elif user_id not in players:
        send_message(chat_id, "❌ Сначала /set_country НАЗВАНИЕ")
    else:
        country = players[user_id]
        try:
            update_article_file(country, text)
            send_message(chat_id, f"✅ Записано в {country}.")
        except Exception:
            pass

# ================= ТОЧКА ВХОДА (LONG POLLING ДЛЯ RENDER) =================
print("Бот запущен в режиме Long Polling...")

# Читаем offset
offset = 0
if os.path.exists(OFFSET_FILE):
    with open(OFFSET_FILE, 'r') as f:
        offset = int(f.read().strip())

# Бесконечный цикл (Render позволяет работать процессам 24/7 на бесплатном тарифе)
while True:
    try:
        url = f"{API_URL}getUpdates?offset={offset + 1}&timeout=30"
        response = urllib.request.urlopen(url, timeout=35)
        data = json.loads(response.read().decode('utf-8'))
        
        if data.get('ok'):
            for upd in data.get('result', []):
                if 'message' in upd:
                    process_message(upd['message'])
                offset = upd['update_id']
                with open(OFFSET_FILE, 'w') as f:
                    f.write(str(offset))
    except Exception as e:
        # Если пропало соединение, ждем 5 секунд и пробуем снова
        time.sleep(5)
from typing import Any
import socket
import struct
import json
import threading
import sqlite3
import uuid
inv_lock = threading.Lock()
MAX_LEN = 65536
FORMAT = 'utf-8'
DB_PATH = "all_info.db"
PORT = 12345
SERVER = '172.18.107.107'

INVITATIONS = {} 
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")      
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS User (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT NOT NULL UNIQUE,         
            password TEXT NOT NULL,
            room_id TEXT,   
            user_code TEXT,
            is_connected INTEGER NOT NULL DEFAULT 0       
        );
        """)        
       
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_name ON User(name);")
        conn.execute("UPDATE User SET is_connected = 0")
        conn.commit()


def send_json(conn, obj):
    msg = json.dumps(obj)  # 將 Python dict 轉成 JSON 字串
    data = msg.encode('utf-8')
    header = struct.pack("!I", len(data))
    conn.sendall(header)
    conn.sendall(data)
    
def send(conn, msg):
    data = msg.encode(FORMAT)
    n = len(data)
    if n <= 0 or n > MAX_LEN:
        raise ValueError("invalid payload length")
    header = struct.pack("!I", n)
    conn.sendall(header)
    conn.sendall(data)

def recvn(conn, n):
    buf = b''
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def recv_bytes(conn):
    header = recvn(conn, 4)
    if header is None:
        return None
    (length,) = struct.unpack("!I", header)
    if length <= 0 or length > MAX_LEN:
        return None
    body = recvn(conn, length)
    return body  # 回傳 bytes，不要 decode

def recv_text(conn):
    b = recv_bytes(conn)
    if b is None:
        return None
    try:
        return b.decode(FORMAT)  # 在這裡 decode
    except UnicodeDecodeError:
        return None

def recv_json(conn):
    s = recv_text(conn)
    if s is None:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None

def ok(data):
    return {"ok": True, "data": data}

def err(code, msg):
    return {"ok": False, "error": {"code": code, "message": msg}}

def db_request(req: dict) -> dict:
    op = req.get("op")
    if not op:
        return err("no_op", "missing 'op'")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # 只查 user，不處理登入邏輯
        if op == "get_user_by_name":
            name = req.get("name")
            if not name:
                return err("bad_request", "missing 'name'")
            cur.execute("SELECT * FROM User WHERE name = ?", (name,))
            row = cur.fetchone()
            if not row:
                return err("not_found", f"user '{name}' not found")
            user = dict(row)
            return ok({"user": user})

        # 建立 user（不判斷重複，由 main_server 先查）
        elif op == "create_user":
            name = req.get("name")
            password = req.get("password")
            user_type_raw = req.get("user_type")  

            if not name or not password:
                print("missing name or password")
                return err("bad_request", "missing name or password")

            # 把 user_type 轉成 int，預設 0（一般使用者）
            try:
                user_type = int(user_type_raw) if user_type_raw is not None else 0
            except ValueError:
                user_type = 0

            # 如果是 developer（user_type == 1），就給一組 UUID，否則 None
            dev_code = str(uuid.uuid4()) if user_type == 1 else None

            try:
                cur.execute(
                    """
                    INSERT INTO User
                    (name, password, room_id, user_code, is_connected)
                    VALUES (?, ?, NULL, ?, 1)
                    """,
                    (name, password, dev_code)
                )
            except sqlite3.IntegrityError:
                # name UNIQUE 衝突
                print("user already exists")
                return err("user_exists", f"user '{name}' already exists")

            user_id = cur.lastrowid
            conn.commit()

            cur.execute("SELECT * FROM User WHERE id = ?", (user_id,))
            row = cur.fetchone()
            user = dict(row)
            return ok({"user": user})


        # 設定 is_connected（登入/登出都可以用）
        elif op == "set_user_connected":
            user_id = req.get("user_id")
            username = req.get("username")  # 支持用名字更新
            is_connected = req.get("is_connected")
            
            if is_connected is None:
                return err("bad_request", "missing 'is_connected'")
            
            # 支持用 user_id 或 username 更新
            if user_id:
                cur.execute(
                    "UPDATE User SET is_connected = ? WHERE id = ?",
                    (int(bool(is_connected)), user_id)
                )
                if cur.rowcount == 0:
                    return err("not_found", f"user id {user_id} not found")
                conn.commit()
                cur.execute("SELECT * FROM User WHERE id = ?", (user_id,))
            elif username:
                cur.execute(
                    "UPDATE User SET is_connected = ? WHERE name = ?",
                    (int(bool(is_connected)), username)
                )
                if cur.rowcount == 0:
                    return err("not_found", f"user '{username}' not found")
                conn.commit()
                cur.execute("SELECT * FROM User WHERE name = ?", (username,))
            else:
                return err("bad_request", "missing 'user_id' or 'username'")
            
            row = cur.fetchone()
            user = dict(row)
            return ok({"user": user})

        else:
            return err("unknown_op", f"unknown op '{op}'")
    finally:
        conn.close()

def db_loop(db_sock):
    while True:
        raw = recv_json(db_sock)
        if raw is None:
            break
        try:
            resp = db_request(raw)
        except Exception as e:
            resp = err("db_exception", str(e))

        send_json(db_sock, resp)


ADDR = (SERVER, PORT)
DISCONNECT_MESSAGE = "!DISCONNECT"

DB = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
DB.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
DB.connect(ADDR)
send(DB, "DB")    
init_db()
db_loop(DB)  
import socket
import threading
import os
import subprocess
import sys
import time
import json
from common import send_json, recv_json, recv_file, send_file, ensure_dir ,recv_text

DB = None
db_lock = threading.Lock()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #這裡是用UDP因為他只是想要去隨便去丟一個封包，讓電腦需要去找一個local ip 去送，這樣我們就可以拿到這個socket的local ip address
    try:
        s.connect(("8.8.8.8", 80))
       
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip
PORT = 12345
SERVER = get_local_ip()
REPO_DIR = 'games_repo'
GAMES_DB_FILE = 'games_db.json' 

games_db = {}      
rooms = {}         
room_id_counter = 1
game_port_counter = 9000  

ensure_dir(REPO_DIR)

def load_games_db():
    global games_db
    if os.path.exists(GAMES_DB_FILE):
        try:
            with open(GAMES_DB_FILE, 'r', encoding='utf-8') as f:
                games_db = json.load(f)
            print(f"[LOAD] 已加載 {len(games_db)} 個遊戲")
        except Exception as e:
            print(f"[ERROR] 加載遊戲數據庫失敗: {e}")
            games_db = {}
    else:
        games_db = {}
        print("[INIT] 遊戲數據庫文件不存在，創建新的數據庫")

def save_games_db():
    try:
        with open(GAMES_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(games_db, f, ensure_ascii=False, indent=2)
        print(f"[SAVE] 已保存 {len(games_db)} 個遊戲到數據庫")
    except Exception as e:
        print(f"[ERROR] 保存遊戲數據庫失敗: {e}")

load_games_db()

#這部分就是現去分辨說這個是誰的連線
DB = None
def distinguish_conn(conn, addr):
    global DB 
    first = recv_text(conn)
    if first is None:
        print(f"[{addr}] connection closed before first message")
        conn.close()
        return False
    if first == "DB":
        DB = conn
        print(f"[{addr}] DB connection established")
        return True
    else:
        print(f"[{addr}] Received: {first} (not DB connection)")
        return False
#因為會一直和DB要訊息，所以乾脆寫成一個韓式包起來
def db_call(payload: dict) -> dict | None:
    global DB
    if DB is None:
        print("[ERROR] DB connection not established")
        return None
    with db_lock:
        try:
            send_json(DB, payload)
            return recv_json(DB)
        except Exception as e:
            print(f"[ERROR] db_call failed: {e}")
            return None
        
def ok(data):
    return {"ok": True, "data": data}

def err(code, msg):
    return {"ok": False, "error": {"code": code, "message": msg}}

def distinguish(conn, addr):
    req = recv_json(conn)
    if req is None:
        print(f"[{addr}] connection closed before first message")
        conn.close()
        return None
    
    print(f"[{addr}] Received request: {req.get('collection')}.{req.get('action')}")

    collection = req.get("collection")
    action = req.get("action")

    if collection == "User" and action == "create_or_login":
        data = req.get("data", {})
        username = data.get("username")
        password = data.get("password")
        user_type = data.get("user_type")

        if not username or not password:
            send_json(conn, err("bad_request", "missing username or password"))
            conn.close()
            return  False

        resp = db_call({
            "op": "get_user_by_name",
            "name": username
        })

        if resp is None:
            send_json(conn, err("db_error", "database unavailable"))
            conn.close()
            return

        if not resp["ok"] and resp["error"]["code"] == "not_found":
            create_resp = db_call({
                "op": "create_user",
                "name": username,
                "password": password,
                "user_type": user_type
            })

            if create_resp is None or not create_resp["ok"]:
                send_json(conn, err("db_error", "failed to create user"))
                conn.close()
                return

            user = create_resp["data"]["user"]
            # 這裡就表示：是「新註冊並登入成功」
            send_json(conn, ok({
                "user": user,
                "created": True
            }))
            # 登入成功後不關閉連接，繼續處理後續的遊戲命令
            return True

        if not resp["ok"]:
            send_json(conn, resp)
            conn.close()
            return False

        user = resp["data"]["user"]

        if user["password"] != password :
            send_json(conn, err("wrong_password", "incorrect password"))
            conn.close()
            return False
        if user["is_connected"] != 0:
            send_json(conn, err("connect_again", "incorrect connectrion"))
            conn.close()
            return False
        set_resp = db_call({
            "op": "set_user_connected",
            "user_id": user["id"],
            "is_connected": 1
        })

        if set_resp is None or not set_resp["ok"]:
            send_json(conn, err("db_error", "failed to update online status"))
            conn.close()
            return False

        user = set_resp["data"]["user"]

        send_json(conn, ok({
            "user": user,
            "created": False 
        }))
        return True

    else:
        send_json(conn, err("unknown_action",
                            f"unknown collection/action: {collection}.{action}"))
        conn.close()
        return False


def handle_client(conn, addr):
    
    global room_id_counter, game_port_counter
    print(f"[NEW] {addr} connected.")
    
    # 先處理登入
    login_result = distinguish(conn, addr)
    if login_result is None or login_result is False:
        # 登入失敗或連接已關閉，直接返回
        return
    
    # 登入成功，繼續處理遊戲命令
    try:
        while True:
            req = recv_json(conn)
            if not req: break
            
            cmd = req.get('cmd')
            
            if cmd == 'upload':
                name = req['name']
                desc = req['desc']
                user_id = req['user_id']
                print(f"[{addr}] Uploading {name}...")
                save_path = os.path.join(REPO_DIR, f"{name}.py")
                if recv_file(conn, save_path):
                    games_db[name] = {'path': save_path, 'desc': desc, 'user_id': user_id}#這裡就是可以去做不同欄位的設定
                    save_games_db() 
                    send_json(conn, {'status': 'ok', 'msg': '上架成功'})
                else:
                    send_json(conn, {'status': 'fail', 'msg': '文件接收失敗'})
                    print(f"[{addr}] Failed to receive file for {name}")
            
            elif cmd == 'delete_game':
                name = req['name']
                user_id = req.get('user_id')
                if name in games_db:
                    if games_db[name].get('user_id') == user_id:
                        del games_db[name]
                        save_games_db()  
                        send_json(conn, {'status': 'ok', 'msg': '下架成功'})
                    else:
                        send_json(conn, {'status': 'fail', 'msg': '無權限刪除此遊戲'})
                else:
                    send_json(conn, {'status': 'fail', 'msg': '遊戲不存在'})
            
            elif cmd == 'list_games':
                user_id = req.get('user_id')
                user_games = {name: info for name, info in games_db.items() 
                             if info.get('user_id') == user_id}
                send_json(conn, {'status': 'ok', 'games': user_games})
                
            elif cmd == 'update_game':
                name = req['name']
                desc = req['desc']
                user_id = req.get('user_id')
                if name not in games_db:
                    send_json(conn, {'status': 'fail', 'msg': '遊戲不存在'})
                    print(f"[{addr}] Update failed: game '{name}' not found")
                elif games_db[name].get('user_id') != user_id:
                    send_json(conn, {'status': 'fail', 'msg': '無權限更新此遊戲'})
                    print(f"[{addr}] Update failed: no permission for '{name}'")
                else:
                    send_json(conn, {'status': 'ready', 'msg': '可以上傳文件'})
                    
                    old_path = games_db[name]['path']
                    if os.path.exists(old_path):
                        os.remove(old_path)
                    
                    # 接收新的遊戲文件並覆蓋
                    save_path = os.path.join(REPO_DIR, f"{name}.py")
                    if recv_file(conn, save_path):
                        # 更新遊戲信息
                        games_db[name] = {'path': save_path, 'desc': desc, 'user_id': user_id}
                        save_games_db()  # 保存到文件
                        send_json(conn, {'status': 'ok', 'msg': '更新成功'})
                        print(f"[{addr}] Game '{name}' updated successfully")
                    else:
                        send_json(conn, {'status': 'fail', 'msg': '文件接收失敗'})
                        print(f"[{addr}] Failed to receive file for update {name}")
            
            elif cmd == 'download_ready':
                # 處理下載完成確認去找到該連接所在的房間
                for rid, room in rooms.items():
                    if conn in room['players']:
                        if 'download_status' not in room:
                            room['download_status'] = {}
                        room['download_status'][conn] = True
                        print(f"[Room {rid}] Player download ready")
                        
                        if len(room['download_status']) == 2 and all(room['download_status'].values()):
                            # 所有玩家都下載完成，開始遊戲
                            game_name = room['game']
                            p1, p2 = room['players']
                            
                            game_port = game_port_counter
                            game_port_counter += 1
                            
                            print(f"[Room {rid}] Starting Game: {game_name} on Port {game_port}")
                            
                            game_script = games_db[game_name]['path']
                            subprocess.Popen([sys.executable, game_script, 'server', str(game_port)])
                            
                            time.sleep(1)
                            
                            send_json(p1, {'status': 'game_start', 'port': game_port, 'role': 'P1', 'game': game_name})
                            send_json(p2, {'status': 'game_start', 'port': game_port, 'role': 'P2', 'game': game_name})
                            
                            del rooms[rid]
                        break
            
            elif cmd == 'download_failed':
                for rid, room in rooms.items():
                    if conn in room['players']:
                        p1, p2 = room['players']
                        try:
                            send_json(p1, {'status': 'download_failed', 'msg': '遊戲下載失敗，請重新選擇'})
                            send_json(p2, {'status': 'download_failed', 'msg': '遊戲下載失敗，請重新選擇'})
                        except:
                            pass
                        del rooms[rid]
                        print(f"[Room {rid}] Download failed, room cleaned up")
                        break
            
            elif cmd == 'logout':
                # 更新用戶的 is_connected 狀態為 0
                # 統一使用 username 登出
                username = req.get('username')
                
                if not username:
                    send_json(conn, {'status': 'fail', 'msg': '缺少用戶名'})
                    print(f"[{addr}] Logout failed: missing username")
                    continue
                
                print(f"[{addr}] Logout request for username: {username}")
                set_resp = db_call({
                    "op": "set_user_connected",
                    "username": username,
                    "is_connected": 0
                })
                
                print(f"[{addr}] Logout db_call response: {set_resp}")
                if set_resp and set_resp.get("ok"):
                    send_json(conn, {'status': 'ok', 'msg': '登出成功'})
                    print(f"[{addr}] Logout successful for {username}")
                else:
                    send_json(conn, {'status': 'fail', 'msg': f'登出失敗: {set_resp.get("error") if set_resp else "無響應"}'})
                    print(f"[{addr}] Logout failed: {set_resp}")
            
            # --- 玩家功能: 瀏覽與下載 ---
            elif cmd == 'list_all_games':
                send_json(conn, {'status': 'ok', 'games': games_db})
            elif cmd == 'download':
                name = req['name']
                print(f"[{addr}] Download request for: {name}")
                if name in games_db:
                    print(f"[{addr}] Sending file: {games_db[name]['path']}")
                    send_json(conn, {'status': 'ok'})
                    send_file(conn, games_db[name]['path'])
                    print(f"[{addr}] File sent successfully")
                else:
                    print(f"[{addr}] Game not found: {name}")
                    send_json(conn, {'status': 'fail', 'msg': '遊戲不存在'})

            elif cmd == 'list_rooms':
                # 顯示房間列表，包含遊戲名稱和玩家數量
                # 過濾掉已下架遊戲的房間
                room_list = {}
                rooms_to_remove = []
                for rid, r in rooms.items():
                    game_name = r['game']
                    # 檢查遊戲是否還存在（未被下架）
                    if game_name not in games_db:
                        # 遊戲已下架，通知房間內的所有玩家
                        for player in r['players']:
                            try:
                                send_json(player, {'status': 'fail', 'msg': '該遊戲已下架，房間已關閉'})
                            except:
                                pass
                        # 標記房間需要移除
                        rooms_to_remove.append(rid)
                        continue
                    player_count = len(r['players'])
                    room_list[rid] = f"{game_name} ({player_count}/2)"
                # 清理已下架遊戲的房間
                for rid in rooms_to_remove:
                    del rooms[rid]
                send_json(conn, {'status': 'ok', 'rooms': room_list})

            elif cmd == 'create_room':
                game_name = req['game_name']
                # 檢查遊戲是否存在
                if game_name not in games_db:
                    send_json(conn, {'status': 'fail', 'msg': '遊戲不存在'})
                    continue
                rid = room_id_counter
                room_id_counter += 1
                # 存儲房間信息，包含遊戲名稱
                rooms[rid] = {'game': game_name, 'players': [conn]}
                send_json(conn, {'status': 'ok', 'room_id': rid, 'msg': '等待玩家加入...'})

            elif cmd == 'join_room':
                room_list = {rid: f"{r['game']} ({len(r['players'])}/2)" for rid, r in rooms.items()}
                send_json(conn, {'status': 'ok', 'rooms': room_list})
                rid = int(req['room_id'])
                if rid not in rooms:
                    send_json(conn, {'status': 'fail', 'msg': '房間不存在'})
                    continue
                
                # 檢查遊戲是否還存在（未被下架）
                game_name = rooms[rid]['game']
                if game_name not in games_db:
                    send_json(conn, {'status': 'fail', 'msg': '該遊戲已下架，房間已關閉'})
                    # 通知房間內的其他玩家（如果有的話）
                    for player in rooms[rid]['players']:
                        if player != conn:
                            try:
                                send_json(player, {'status': 'fail', 'msg': '該遊戲已下架，房間已關閉'})
                            except:
                                pass
                    # 清理已下架遊戲的房間
                    del rooms[rid]
                    continue
                
                if len(rooms[rid]['players']) < 2:
                    rooms[rid]['players'].append(conn)
                    
                    # 房間滿了，通知兩個玩家需要下載遊戲
                    if len(rooms[rid]['players']) == 2:
                        game_name = rooms[rid]['game']
                        
                        # 再次檢查遊戲是否還存在（防止在下載過程中遊戲被下架）
                        if game_name not in games_db:
                            send_json(conn, {'status': 'fail', 'msg': '該遊戲已下架，房間已關閉'})
                            # 通知另一個玩家
                            try:
                                other_player = rooms[rid]['players'][0] if rooms[rid]['players'][0] != conn else rooms[rid]['players'][1]
                                send_json(other_player, {'status': 'download_failed', 'msg': '該遊戲已下架，房間已關閉'})
                            except:
                                pass
                            del rooms[rid]
                            continue
                        
                        p1, p2 = rooms[rid]['players']
                        
                        rooms[rid]['download_status'] = {p1: False, p2: False}
                        
                        send_json(p1, {'status': 'need_download', 'game': game_name})
                        send_json(p2, {'status': 'need_download', 'game': game_name})
                        
                        print(f"[Room {rid}] Waiting for players to download {game_name}...")
                        # 不再在這裡等待，讓主循環處理 download_ready 消息
                else:
                    send_json(conn, {'status': 'fail', 'msg': '房間已滿或不存在'})

    except Exception as e:
        print(f"[{addr}] Error: {e}")
    finally:
        conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SERVER, PORT))
    server.listen()
    print(f"[LOBBY SERVER] Running on {SERVER}:{PORT}")
    while True:
        conn, addr = server.accept()
        if distinguish_conn(conn, addr):
            print("DB/GS connected")
        else:
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()
            print(f"[ACTIVE CONNECTIONS] {threading.active_count()-1}")

if __name__ == "__main__":
    start_server()
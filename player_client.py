import socket
import os
import sys
import subprocess
import threading
from common import send_json, recv_json, recv_file, ensure_dir, send

HOST = '172.18.107.107'
PORT = 12345
# 每個玩家使用自己的下載目錄
def get_download_dir(username):
    """根據用戶名獲取下載目錄"""
    download_dir = os.path.join('player_downloads', username)
    ensure_dir(download_dir)
    return download_dir
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    client.connect((HOST, PORT))
    send(client, "hi")
except:
    print("連線失敗")
    
def wait_for_game_start(sock, download_dir):
    """在房間內等待 Server 通知遊戲開始"""
    print("正在等待其他玩家加入...")
    while True:
        res = recv_json(sock)
        if not res: break
        
        if res.get('status') == 'need_download':
            game_name = res['game']
            print(f"\n需要下載遊戲: {game_name}")
            script_path = os.path.join(download_dir, f"{game_name}.py")
            
            print(f"正在下載遊戲: {game_name}...")
            send_json(sock, {'cmd': 'download', 'name': game_name})
            download_res = recv_json(sock)
            if download_res and download_res.get('status') == 'ok':
                file_path = os.path.join(download_dir, f"{game_name}.py")
                if recv_file(sock, file_path):
                    print(f"下載完成！文件保存在: {file_path}")
                    send_json(sock, {'cmd': 'download_ready'})
                else:
                    print("下載失敗：文件接收錯誤")
                    send_json(sock, {'cmd': 'download_failed'})
                    return
            else:
                print(f"下載失敗: {download_res.get('msg', '未知錯誤') if download_res else '無響應'}")
                send_json(sock, {'cmd': 'download_failed'})
                return  
        
        elif res.get('status') == 'download_failed':
            print(f"\n{res.get('msg', '遊戲下載失敗，返回選單')}")
            return
        
        elif res.get('status') == 'fail':
            print(f"\n{res.get('msg', '操作失敗，返回選單')}")
            return
        
        elif res.get('status') == 'game_start':
            print("\n!!! 遊戲開始 !!!")
            game_name = res['game']
            game_port = res['port']
            role = res['role'] 
            
            script_path = os.path.join(download_dir, f"{game_name}.py")
            print(f"正在啟動 {game_name} (Port {game_port})...")
            
            # 呼叫 subprocess 執行下載下來的 python 檔
            # 參數格式: python tictactoe.py client <IP> <PORT> <ROLE>
            subprocess.call([
                sys.executable, script_path, 
                'client', HOST, str(game_port), role
            ]) 
            
            print("遊戲結束，回到大廳。")
            break
        else:
            print(f"收到訊息: {res}")

def main(username):
    DOWNLOAD_DIR = get_download_dir(username)
    print("=== 遊戲大廳 ===")
    while True:
        print("\n1. 瀏覽遊戲 (List Games)\n2. 下載遊戲 (Download)\n3. 瀏覽房間 (List Rooms)\n4. 建立房間 (Create)\n5. 加入房間 (Join)\n6. 離開")
        choice = input("選擇: ")

        if choice == '1':
            send_json(client, {'cmd': 'list_all_games'})
            res = recv_json(client)
            if res and res.get('status') == 'ok' and 'games' in res:
                print("--- 商城列表 ---")
                if res['games']:
                    for k, v in res['games'].items():
                        print(f"[{k}] {v['desc']}")
                else:
                    print("目前沒有可用的遊戲")
            else:
                print("獲取遊戲列表失敗")

        elif choice == '2':
            send_json(client, {'cmd': 'list_all_games'})
            res = recv_json(client)
            if res and res.get('status') == 'ok' and 'games' in res:
                print("--- 商城列表 ---")
                if res['games']:
                    for k, v in res['games'].items():
                        print(f"[{k}] {v['desc']}")
                    name = input("輸入遊戲名稱: ")
                    send_json(client, {'cmd': 'download', 'name': name})
                    download_res = recv_json(client)
                    if download_res and download_res.get('status') == 'ok':
                        file_path = os.path.join(DOWNLOAD_DIR, f"{name}.py")
                        if recv_file(client, file_path):
                            print(f"下載完成！文件保存在: {file_path}")
                        else:
                            print("下載失敗：文件接收錯誤")
                    else:
                        print(f"下載失敗: {download_res.get('msg', '未知錯誤') if download_res else '無回應'}")
                else:
                    print("目前沒有可用的遊戲")
            else:
                print("獲取遊戲列表失敗")

        elif choice == '3':
            send_json(client, {'cmd': 'list_rooms'})
            res = recv_json(client)
            if res and res.get('status') == 'ok' and 'rooms' in res:
                print("--- 房間列表 ---")
                if res['rooms']:
                    for rid, info in res['rooms'].items():
                        print(f"ID: {rid} | {info}")
                else:
                    print("目前沒有可用的房間")
            else:
                print("獲取房間列表失敗")

        elif choice == '4':
            send_json(client, {'cmd': 'list_all_games'})
            res = recv_json(client)
            if res and res.get('status') == 'ok' and 'games' in res:
                print("--- 商城列表 ---")
                if res['games']:
                    for k, v in res['games'].items():
                        print(f"[{k}] {v['desc']}")
                    game = input("想玩什麼遊戲 (名稱): ")
                else:
                    print("目前沒有可用的遊戲")
                    continue
            else:
                print("獲取遊戲列表失敗")
                continue
            # 不需要提前下載，在遊戲開始時會自動下載
            
            send_json(client, {'cmd': 'create_room', 'game_name': game})
            res = recv_json(client)
            if res['status'] == 'ok':
                print(f"房間建立成功 (ID: {res['room_id']})")
                wait_for_game_start(client, DOWNLOAD_DIR) # 進入等待模式
            else:
                print(f"創建房間失敗: {res.get('msg', '未知錯誤')}")

        elif choice == '5':
            send_json(client, {'cmd': 'list_rooms'})
            res = recv_json(client)
            if res and res.get('status') == 'ok' and 'rooms' in res:
                print("--- 房間列表 ---")
                if res['rooms']:
                    for rid, info in res['rooms'].items():
                        print(f"ID: {rid} | {info}")
                else:
                    print("目前沒有可用的房間")
            else:
                print("獲取房間列表失敗")
            rid = input("輸入房間 ID: ")
            
            
            send_json(client, {'cmd': 'join_room', 'room_id': rid})
            wait_for_game_start(client, DOWNLOAD_DIR)

        elif choice == '6':
            # 通知服務器更新 is_connected 為 0
            print(f"正在登出用戶: {username}")
            send_json(client, {'cmd': 'logout', 'username': username})
            res = recv_json(client)
            print(f"登出回應: {res}")
            if res and res.get('status') == 'ok':
                print("已登出")
            else:
                print(f"登出失敗: {res.get('msg', '未知錯誤') if res else '無回應'}")
            break

    client.close()

if __name__ == "__main__":
    username = input("Please enter your username:")
    password = input("Please enter your password:")
    user_type_input = 0
    send_json(client, {
    "collection": "User",
    "action": "create_or_login",
    "data": {
        "username": username,
        "password": password,
        "user_type": user_type_input
    }
    })
    
    reply = recv_json(client)
    print("Server 回應:", reply)
    if not reply or not reply.get("ok"):
        print("Login failed.")
        client.close()
        raise SystemExit
    # 保存用戶名用於登出
    data = reply["data"]
    user = data["user"]
    username = user["name"]
    main(username)
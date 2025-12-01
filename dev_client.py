import socket
import os
from common import send_json, recv_json, send_file, send

HOST = '140.113.17.12'
PORT = 12345
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))
send(client, "hi")
def main(user_id, username):
    print("=== 開發者後台 ===")
    while True:
        print("\n1. 上架遊戲 (Upload)\n2. 離開\n3. 查看遊戲列表\n4. 下架遊戲\n5. 更新遊戲")
        opt = input("選擇: ")
        
        if opt == '1':
            path = input("遊戲檔案路徑 (例如 tictactoe.py): ")
            if not os.path.exists(path):
                print("檔案不存在")
                continue
            name = input("遊戲名稱 (ID): ")
            if name == "":
                name = f"{path}default.py"
            desc = input("遊戲簡介: ")
            if desc == "":
                desc = name
            send_json(client, {'cmd': 'upload', 'name': name, 'desc': desc,"user_id": user_id})
            send_file(client, path)
            res = recv_json(client)
            print(f"Server 回應: {res['msg']}")
        elif opt == '2':
            # 通知服務器更新 is_connected 為 0
            send_json(client, {'cmd': 'logout', 'username': username})
            res = recv_json(client)
            if res.get('status') == 'ok':
                print("已登出")
            break
        elif opt == '3':
            send_json(client, {'cmd': 'list_games', 'user_id': user_id})
            res = recv_json(client)
            if res.get('status') == 'ok':
                games = res.get('games', {})
                if games:
                    print("\n=== 您上傳的遊戲 ===")
                    for name, info in games.items():
                        desc = info.get('desc', '') or '無描述'
                        print(f"- {name}: {desc}")
                else:
                    print("您尚未上傳任何遊戲")
            else:
                print(f"Server 回應: {res.get('msg', '錯誤')}")
        elif opt == '4':
            send_json(client, {'cmd': 'list_games', 'user_id': user_id})
            res = recv_json(client)
            if res.get('status') == 'ok':
                games = res.get('games', {})
                if games:
                    print("\n=== 您上傳的遊戲 ===")
                    for name, info in games.items():
                        desc = info.get('desc', '') or '無描述'
                        print(f"- {name}: {desc}")
                else:
                    print("您尚未上傳任何遊戲")
                    continue
            name = input("遊戲名稱 (ID): ")
            send_json(client, {'cmd': 'delete_game', 'name': name, 'user_id': user_id})
            res = recv_json(client)
            print(f"Server 回應: {res.get('msg', '錯誤')}")
        elif opt == '5':
            send_json(client, {'cmd': 'list_games', 'user_id': user_id})
            res = recv_json(client)
            if res.get('status') == 'ok':
                games = res.get('games', {})
                if games:
                    print("\n=== 您上傳的遊戲 ===")
                    for name, info in games.items():
                        print(f"- {name}:{info.get('desc', '無描述')}")
                else:
                    print("您尚未上傳任何遊戲")
                    continue
            else:
                print(f"Server 回應: {res.get('msg', '錯誤')}")
                continue
            
            name = input("要更新的遊戲名稱 (ID): ")
            path = input("新的遊戲檔案路徑 (例如 tictactoe.py): ")
            if not os.path.exists(path):
                print("檔案不存在")
                continue
            desc = input("新的遊戲簡介: ")
            
            send_json(client, {'cmd': 'update_game', 'name': name, 'desc': desc, 'user_id': user_id})
            send_file(client, path)
            res = recv_json(client)
            print(f"Server 回應: {res.get('msg', '錯誤')}")
    client.close()

if __name__ == "__main__":
    username = input("Please enter your username:")
    password = input("Please enter your password:")
    user_type_input = 1

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
    data = reply["data"]
    user = data["user"]
    user_id = user["user_code"] 
    username = user["name"] 
    print(f"Login successful. User ID: {user_id}")
    main(user_id, username)  

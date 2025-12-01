"""
遊戲模板 (Game Template)
這是一個用於創建新遊戲的模板文件。

使用說明：
1. 複製此文件並重命名為你的遊戲名稱（例如：my_game.py）
2. 實現以下函數：
   - check_win(): 檢查遊戲是否結束並返回勝者
   - print_board(): 打印遊戲狀態
   - run_server(): 遊戲服務器邏輯
   - run_client(): 遊戲客戶端邏輯
3. 確保遊戲支持以下參數格式：
   - server: python game.py server <port>
   - client: python game.py client <ip> <port> <P1|P2>
"""

import sys
import socket
import json

# ============================================
# 遊戲邏輯函數 (需要根據你的遊戲實現)
# ============================================

def check_win(game_state):
    """
    檢查遊戲是否結束
    
    Args:
        game_state: 遊戲狀態（可以是 board、score 等，根據你的遊戲而定）
    
    Returns:
        - 如果有玩家獲勝，返回 'P1' 或 'P2'
        - 如果是平局，返回 'Draw'
        - 如果遊戲繼續，返回 None
    """
    # TODO: 實現你的勝負判斷邏輯
    # 範例：
    # if game_state['winner']:
    #     return game_state['winner']
    # if game_state['is_draw']:
    #     return 'Draw'
    return None

def print_board(game_state):
    """
    打印遊戲狀態（棋盤、分數等）
    
    Args:
        game_state: 遊戲狀態字典
    """
    # TODO: 實現你的顯示邏輯
    # 範例：
    # board = game_state.get('board', [])
    # print(f"Board: {board}")
    pass

# ============================================
# 遊戲服務器 (Game Server)
# ============================================

def run_server(port):
    """
    運行遊戲服務器
    
    流程：
    1. 創建 socket 並綁定端口
    2. 等待兩個玩家連接
    3. 遊戲主循環：
       a. 廣播當前遊戲狀態給所有玩家
       b. 接收當前玩家的操作
       c. 更新遊戲狀態
       d. 檢查勝負
       e. 切換玩家
    4. 遊戲結束後清理資源
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('0.0.0.0', int(port)))
        server.listen(2)
        print(f"[GAME SERVER] Listening on {port}")
        
        players = []
        player_files = []  # 使用 makefile 避免 TCP 粘包問題
        
        # 等待兩個玩家連接
        print("等待玩家 1 連線...")
        conn1, addr1 = server.accept()
        players.append(conn1)
        player_files.append(conn1.makefile('r', encoding='utf-8'))
        print(f"Player 1 connected: {addr1}")
        
        print("等待玩家 2 連線...")
        conn2, addr2 = server.accept()
        players.append(conn2)
        player_files.append(conn2.makefile('r', encoding='utf-8'))
        print(f"Player 2 connected: {addr2}")
        
        # 初始化遊戲狀態
        # TODO: 根據你的遊戲初始化狀態
        game_state = {
            'board': [' '] * 9,  # 範例：井字棋的 9 格
            'turn': 0,  # 0 = P1, 1 = P2
        }
        
        try:
            while True:
                # 1. 廣播當前遊戲狀態
                state = {
                    'board': game_state['board'],
                    'turn': 'P1' if game_state['turn'] == 0 else 'P2'
                }
                msg = json.dumps(state) + "\n"
                for p in players:
                    try:
                        p.sendall(msg.encode())
                    except:
                        pass
                
                # 2. 接收當前玩家的操作
                current_player_idx = game_state['turn']
                current_file = player_files[current_player_idx]
                print(f"等待 {'P1' if game_state['turn']==0 else 'P2'} 輸入...")
                
                try:
                    line = current_file.readline()
                    if not line:
                        print("玩家斷線")
                        break
                    
                    action = line.strip()
                    print(f"收到操作: {action}")
                    
                    # TODO: 處理玩家的操作並更新遊戲狀態
                    # 範例：
                    # if action.isdigit():
                    #     move = int(action)
                    #     if 0 <= move <= 8 and game_state['board'][move] == ' ':
                    #         game_state['board'][move] = 'O' if game_state['turn'] == 0 else 'X'
                    
                    # 3. 檢查勝負
                    winner = check_win(game_state)
                    if winner:
                        # 廣播遊戲結束
                        final_state = {
                            'board': game_state['board'],
                            'turn': 'END',
                            'winner': winner
                        }
                        final_msg = json.dumps(final_state) + "\n"
                        for p in players:
                            try:
                                p.sendall(final_msg.encode())
                            except:
                                pass
                        print(f"遊戲結束: {winner} 獲勝")
                        break
                    
                    # 4. 切換玩家
                    game_state['turn'] = 1 - game_state['turn']
                    
                except ConnectionResetError:
                    print("連線被重置")
                    break
                    
        except Exception as e:
            print(f"Server Error: {e}")
        finally:
            # 清理資源
            if 'player_files' in locals():
                for f in player_files:
                    try:
                        f.close()
                    except:
                        pass
            if 'players' in locals():
                for p in players:
                    try:
                        p.close()
                    except:
                        pass
            server.close()
            print("Server 關閉")
            
    except Exception as e:
        print(f"Server setup error: {e}")
        server.close()

# ============================================
# 遊戲客戶端 (Game Client)
# ============================================

def run_client(ip, port, role):
    """
    運行遊戲客戶端
    
    Args:
        ip: 遊戲服務器 IP
        port: 遊戲服務器端口
        role: 玩家角色 ('P1' 或 'P2')
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, int(port)))
    except Exception as e:
        print(f"連線失敗: {e}")
        return
    
    print(f"已連線到 Game Server。你是 {role}")
    
    # 使用 makefile 避免 TCP 粘包問題
    sock_file = s.makefile('r', encoding='utf-8')
    
    try:
        while True:
            # 等待服務器發送遊戲狀態
            line = sock_file.readline()
            if not line:
                print("伺服器已斷線")
                break
            
            try:
                data = json.loads(line.strip())
            except json.JSONDecodeError:
                print("收到損毀的資料，略過")
                continue
            
            # 檢查遊戲是否結束
            if 'winner' in data:
                print_board(data)  # 顯示最後的遊戲狀態
                print(f"\n=== 遊戲結束！贏家是: {data['winner']} ===")
                break
            
            # 顯示當前遊戲狀態
            if 'board' in data:
                print_board(data)
                
                # 如果是我的回合，等待輸入
                if data['turn'] == role:
                    # TODO: 根據你的遊戲實現輸入邏輯
                    # 範例：
                    # while True:
                    #     move = input(f"輪到你了，輸入位置 (0-8): ")
                    #     if move.isdigit() and 0 <= int(move) <= 8:
                    #         s.sendall((move + "\n").encode())
                    #         break
                    #     print("輸入無效")
                else:
                    print(f"等待對手 ({'P2' if role=='P1' else 'P1'}) 行動...")
                    
    except KeyboardInterrupt:
        print("\n離開遊戲")
    except Exception as e:
        print(f"\n連線錯誤: {e}")
    finally:
        sock_file.close()
        s.close()

# ============================================
# 主程序入口
# ============================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python template.py [server <port>] | [client <ip> <port> <P1|P2>]")
        exit()
    
    mode = sys.argv[1]
    if mode == 'server':
        if len(sys.argv) < 3:
            print("Usage: python template.py server <port>")
        else:
            run_server(sys.argv[2])
    elif mode == 'client':
        if len(sys.argv) < 5:
            print("Usage: python template.py client <ip> <port> <role>")
        else:
            run_client(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print("Unknown mode. Use 'server' or 'client'")


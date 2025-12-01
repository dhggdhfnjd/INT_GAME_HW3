import sys
import socket
import json
import time

def check_win(board):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in wins:
        if board[a] == board[b] == board[c] and board[a] != ' ':
            return board[a]
    if ' ' not in board: return 'Draw'
    return None

def print_board(board):
    print(f"\n {board[0]} | {board[1]} | {board[2]} ")
    print("---+---+---")
    print(f" {board[3]} | {board[4]} | {board[5]} ")
    print("---+---+---")
    print(f" {board[6]} | {board[7]} | {board[8]} \n")

def run_server(port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 允許 Port 重用，避免重開時卡住
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', int(port)))
    server.listen(2)
    print(f"[GAME SERVER] Listening on {port}")
    
    players = []
    player_files = []  
     
    # 等待兩個玩家連線
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
    
    board = [' '] * 9
    turn = 0 
    
    try:
        initial_state = {'board': board, 'turn': 'P1' if turn == 0 else 'P2'}
        initial_msg = json.dumps(initial_state) + "\n"
        for p in players:
            try:
                p.sendall(initial_msg.encode())
            except:
                pass
        
        while True:
            current_player_idx = turn
            current_file = player_files[current_player_idx]
            print(f"等待 {'P1' if turn==0 else 'P2'} 輸入...")
            
            try:
                line = current_file.readline()
                #這裡去接受玩家的移動指令
                if not line:
                    print("玩家斷線")
                    break
                
                move_str = line.strip()
                print(f"收到輸入: {move_str}")
                
                if move_str.isdigit():
                    move = int(move_str)
                    if 0 <= move <= 8 and board[move] == ' ':
                        board[move] = 'O' if turn == 0 else 'X'
                        
                        # 3. 移動後檢查勝負
                        winner_symbol = check_win(board)
                        if winner_symbol:
                            # 將符號轉換為玩家名稱
                            if winner_symbol == 'O':
                                winner_name = 'P1'
                            elif winner_symbol == 'X':
                                winner_name = 'P2'
                            else:  
                                winner_name = 'Draw'
                            
                            # 廣播最後狀態和勝負結果
                            final_state = {'board': board, 'turn': 'END', 'winner': winner_name}
                            final_msg = json.dumps(final_state) + "\n"
                            for p in players:
                                try:
                                    p.sendall(final_msg.encode())
                                except:
                                    pass
                            print(f"遊戲結束: {winner_name} 獲勝")
                            break
                        
                        turn = 1 - turn
                        
                        updated_state = {'board': board, 'turn': 'P1' if turn == 0 else 'P2'}
                        updated_msg = json.dumps(updated_state) + "\n"
                        for p in players:
                            try:
                                p.sendall(updated_msg.encode())
                            except:
                                pass
                    else:
                        print(f"無效移動: 位置 {move} 已被佔用或越界")
                        invalid_state = {'board': board, 'turn': 'P1' if turn == 0 else 'P2'}
                        invalid_msg = json.dumps(invalid_state) + "\n"
                        for p in players:
                            try:
                                p.sendall(invalid_msg.encode())
                            except:
                                pass
                else:
                    print(f"收到非數字輸入: {move_str}")
                    invalid_state = {'board': board, 'turn': 'P1' if turn == 0 else 'P2'}
                    invalid_msg = json.dumps(invalid_state) + "\n"
                    for p in players:
                        try:
                            p.sendall(invalid_msg.encode())
                        except:
                            pass
            except ConnectionResetError:
                print("連線被重置")
                break

    except Exception as e:
        print(f"Server Error: {e}")
    finally:
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

def run_client(ip, port, role):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, int(port)))
    except Exception as e:
        print(f"連線失敗: {e}")
        return

    print(f"已連線到 Game Server。你是 {role}")
    symbol = 'O' if role == 'P1' else 'X'
    
    sock_file = s.makefile('r', encoding='utf-8')
    
    try:
        while True:
            print("等待伺服器狀態更新...")
            line = sock_file.readline()
            if not line: 
                print("伺服器已斷線")
                break
            
            try:
                data = json.loads(line.strip())
            except json.JSONDecodeError:
                print("收到損毀的資料，略過")
                continue

            if 'winner' in data:
                print(f"\n=== 遊戲結束！贏家是: {data['winner']} ===")
                break

            if 'board' in data:
                print_board(data['board'])
                if data['turn'] == role:
                    while True:
                        move = input(f"輪到你了 ({symbol}), 輸入位置 (0-8): ")
                        if move.isdigit() and 0 <= int(move) <= 8 and data['board'][int(move)] == ' ':
                            print(f"正在傳送 {move} ...")
                            s.sendall((move + "\n").encode()) 
                            break
                        print("輸入無效 (位置必須是 0-8 且是空格)")
                else:
                    print("等待對手行動...")
    except Exception as e:
        print(f"Client Error: {e}")
    finally:
        sock_file.close()
        s.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tictactoe.py [server|client] ...")
        exit()
        
    mode = sys.argv[1]
    if mode == 'server':
        run_server(sys.argv[2])
    elif mode == 'client':
        run_client(sys.argv[2], sys.argv[3], sys.argv[4])

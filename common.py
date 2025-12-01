import json
import struct
import os
import socket
FORMAT = 'utf-8'
MAX_LEN = 65536

def send_json(sock, data):
    try:
        json_bytes = json.dumps(data).encode('utf-8')
        # Header: 4 bytes unsigned int (Big Endian) 紀錄長度
        sock.sendall(struct.pack('!I', len(json_bytes)) + json_bytes)
    except Exception as e:
        print(f"[Protocol Error] Send JSON failed: {e}")

def recv_json(sock):
    try:
        header = sock.recv(4)
        if not header: return None
        length = struct.unpack('!I', header)[0]
        
        data = b''
        while len(data) < length:
            packet = sock.recv(length - len(data))
            if not packet: return None
            data += packet
        return json.loads(data.decode('utf-8'))
    except Exception as e:
        return None

def send_file(sock, filepath):
    if not os.path.exists(filepath):
        return False
    filesize = os.path.getsize(filepath)
    sock.sendall(struct.pack('!Q', filesize))
    
    with open(filepath, 'rb') as f:
        while True:
            bytes_read = f.read(4096)
            if not bytes_read: break
            sock.sendall(bytes_read)
    return True

def recv_file(sock, savepath, timeout=None):
    try:
        old_timeout = sock.gettimeout()
        if timeout is not None:
            sock.settimeout(timeout)
        
        dir_path = os.path.dirname(savepath)
        if dir_path:
            ensure_dir(dir_path)
        
        header = sock.recv(8)
        if not header or len(header) < 8:
            print(f"[ERROR] Failed to receive file header for {savepath}")
            sock.settimeout(old_timeout)
            return False
        filesize = struct.unpack('!Q', header)[0]
        print(f"正在接收文件 ({filesize} bytes)...")
        
        received = 0
        last_progress = 0
        with open(savepath, 'wb') as f:
            #f就是那個要存檔案的檔案
            while received < filesize:
                try:
                    chunk = sock.recv(min(4096, filesize - received))
                    #避免去多收
                    if not chunk: 
                        print(f"[ERROR] Connection closed while receiving file, received {received}/{filesize} bytes")
                        break
                    f.write(chunk)
                    received += len(chunk)
                    
                    progress = int((received / filesize) * 100)
                    if progress >= last_progress + 10:
                        print(f"下載進度: {progress}% ({received}/{filesize} bytes)")
                        last_progress = progress
                except socket.timeout:
                    print(f"[ERROR] 接收超時，已接收 {received}/{filesize} bytes")
                    sock.settimeout(old_timeout)
                    return False
        
        if timeout is not None:
            sock.settimeout(old_timeout)
        
        if received == filesize:
            print(f"✓ 文件接收完成: {savepath}")
            return True
        else:
            print(f"[ERROR] 文件不完整: 已接收 {received}/{filesize} bytes")
            return False
    except socket.timeout:
        print(f"[ERROR] 接收文件超時（{timeout}秒）")
        if timeout is not None:
            sock.settimeout(old_timeout)
        return False
    except Exception as e:
        print(f"[ERROR] Exception in recv_file: {e}")
        try:
            if timeout is not None:
                sock.settimeout(old_timeout)
        except:
            pass
        return False

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
def recvn(conn, n):
    buf = b''
    while len(buf) < n:
        try:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        except OSError as e:
            print(f"Socket error: {e}")
            return None
    return buf
def recv_bytes(conn):
    header = recvn(conn, 4)
    if header is None:
        return None
    (length,) = struct.unpack("!I", header)
    if length <= 0 or length > MAX_LEN:
        return None
    body = recvn(conn, length)
    return body
def recv_text(conn):
    b = recv_bytes(conn)
    if b is None:
        return None
    try:
        return b.decode(FORMAT) 
    except UnicodeDecodeError:
        return None

def send(sock, msg):
    data = msg.encode(FORMAT)
    n = len(data)
    if n <= 0 or n > MAX_LEN:
        raise ValueError("invalid payload length")
    header = struct.pack("!I", n)
    sock.sendall(header + data)
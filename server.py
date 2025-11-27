import socket
import threading
import json
import struct
import datetime
import ssl # Thêm thư viện bảo mật
import os

HOST = '127.0.0.1'
PORT = 9999
LOG_FILE = "chat_history.log"

# --- CẤU HÌNH SSL ---
CERT_FILE = 'server.crt'
KEY_FILE = 'server.key'

# --- CÁC HÀM HỖ TRỢ (CORE) ---
def send_json(sock, data):
    try:
        json_data = json.dumps(data).encode('utf-8')
        msg_len = struct.pack('!I', len(json_data))
        sock.sendall(msg_len + json_data)
    except Exception as e:
        print(f"Lỗi gửi: {e}")

def recv_json(sock):
    def recvall(n):
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet: return None
            data += packet
        return data
    try:
        raw_msglen = recvall(4)
        if not raw_msglen: return None
        msglen = struct.unpack('!I', raw_msglen)[0]
        raw_data = recvall(msglen)
        if not raw_data: return None
        return json.loads(raw_data.decode('utf-8'))
    except:
        return None

def save_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)

# --- LOGIC SERVER ---
clients = {} 

def broadcast(message_dict, room_name=None, exclude_socket=None):
    for client_socket, info in clients.items():
        if client_socket != exclude_socket:
            if room_name is None or info['room'] == room_name:
                send_json(client_socket, message_dict)

def handle_client(client_socket):
    try:
        data = recv_json(client_socket)
        if not data or data['type'] != 'login': return
        
        nickname = data['nickname']
        clients[client_socket] = {"nick": nickname, "room": "Lobby"}
        
        save_log(f"[SECURE CONNECT] {nickname} vào Lobby.")
        send_json(client_socket, {"type": "info", "msg": f"Chào {nickname}! Kết nối đã được MÃ HÓA SSL."})
        broadcast({"type": "info", "msg": f"{nickname} đã vào phòng."}, room_name="Lobby")

        while True:
            data = recv_json(client_socket)
            if not data: break

            cmd = data['type']
            current_room = clients[client_socket]['room']
            my_name = clients[client_socket]['nick']

            if cmd == 'chat':
                msg_content = f"[{current_room}] {my_name}: {data['msg']}"
                save_log(msg_content)
                broadcast({
                    "type": "chat",
                    "sender": my_name,
                    "msg": data['msg'],
                    "room": current_room
                }, room_name=current_room, exclude_socket=client_socket)

            elif cmd == 'file':
                broadcast({
                    "type": "file",
                    "sender": my_name,
                    "filename": data['filename'],
                    "content": data['content'], 
                    "room": current_room
                }, room_name=current_room, exclude_socket=client_socket)
                save_log(f"[File] {my_name} gửi file được mã hóa trong {current_room}")

            elif cmd == 'join_room':
                new_room = data['room_name']
                broadcast({"type": "info", "msg": f"{my_name} rời phòng."}, room_name=current_room)
                clients[client_socket]['room'] = new_room
                send_json(client_socket, {"type": "info", "msg": f"Đã vào phòng: {new_room}"})
                broadcast({"type": "info", "msg": f"{my_name} vào phòng."}, room_name=new_room)

            elif cmd == 'private_msg':
                recipient = data['recipient']
                found = False
                for sock, info in clients.items():
                    if info['nick'] == recipient:
                        send_json(sock, {"type": "private", "sender": my_name, "msg": data['msg']})
                        send_json(client_socket, {"type": "info", "msg": f"[Mật] Tới {recipient}: {data['msg']}"})
                        found = True; break
                if not found: send_json(client_socket, {"type": "error", "msg": f"Không tìm thấy '{recipient}'"})

            elif cmd == 'list_users':
                users = [info['nick'] for s, info in clients.items() if info['room'] == current_room]
                send_json(client_socket, {"type": "info", "msg": f"Danh sách {current_room}: {', '.join(users)}"})

    except:
        pass
    finally:
        if client_socket in clients:
            info = clients[client_socket]
            del clients[client_socket]
            broadcast({"type": "info", "msg": f"{info['nick']} thoát."}, room_name=info['room'])
        client_socket.close()

# --- MAIN SERVER STARTUP ---
# 1. Tạo socket TCP thường
raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
raw_socket.bind((HOST, PORT))
raw_socket.listen()

# 2. Tạo lớp bảo vệ SSL
context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    print(f"--- SERVER SECURE (SSL/TLS) ĐANG CHẠY TRÊN {HOST}:{PORT} ---")
else:
    print(">>> LỖI: Thiếu file chứng chỉ! Hãy chạy 'py gen_cert.py' trước.")
    exit()

while True:
    try:
        # Chấp nhận kết nối thường
        client_raw, addr = raw_socket.accept()
        # Nâng cấp lên kết nối bảo mật (Handshake)
        client_ssl = context.wrap_socket(client_raw, server_side=True)
        
        print(f"Kết nối bảo mật từ: {addr}")
        t = threading.Thread(target=handle_client, args=(client_ssl,))
        t.start()
    except Exception as e:
        print(f"Lỗi kết nối: {e}")
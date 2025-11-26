import socket
import threading
import json
import struct

HOST = '127.0.0.1'
PORT = 9999

# --- CÁC HÀM HỖ TRỢ (GIỮ NGUYÊN TỪ PHẦN 1) ---
def send_json(sock, data):
    try:
        json_data = json.dumps(data).encode('utf-8')
        msg_len = struct.pack('!I', len(json_data))
        sock.sendall(msg_len + json_data)
    except Exception as e:
        print(f"Lỗi gửi JSON: {e}")

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

# --- LOGIC SERVER (NÂNG CẤP PHẦN 2) ---
# Cấu trúc mới: Key là Socket, Value là Dict {"nick": "Tên", "room": "TênPhòng"}
clients = {} 

def broadcast(message_dict, room_name=None, exclude_socket=None):
    """Gửi tin nhắn cho clients. Nếu có room_name, chỉ gửi cho người trong phòng đó."""
    for client_socket, info in clients.items():
        if client_socket != exclude_socket:
            # Nếu không chỉ định phòng (gửi all) HOẶC cùng phòng thì mới gửi
            if room_name is None or info['room'] == room_name:
                send_json(client_socket, message_dict)

def handle_client(client_socket):
    try:
        # 1. Đăng nhập
        data = recv_json(client_socket)
        if not data or data['type'] != 'login': return
        
        nickname = data['nickname']
        # Mặc định vào phòng 'Lobby'
        clients[client_socket] = {"nick": nickname, "room": "Lobby"}
        
        print(f"[Kết nối] {nickname} vào Lobby.")
        send_json(client_socket, {"type": "info", "msg": f"Chào mừng {nickname} đến với Lobby!"})
        broadcast({"type": "info", "msg": f"{nickname} đã vào phòng Lobby."}, room_name="Lobby")

        # 2. Vòng lặp xử lý lệnh
        while True:
            data = recv_json(client_socket)
            if not data: break

            cmd = data['type']
            current_room = clients[client_socket]['room']
            my_name = clients[client_socket]['nick']

            # --- XỬ LÝ CHAT THƯỜNG (Trong phòng) ---
            if cmd == 'chat':
                broadcast({
                    "type": "chat",
                    "sender": my_name,
                    "msg": data['msg'],
                    "room": current_room
                }, room_name=current_room, exclude_socket=client_socket)

            # --- XỬ LÝ CHUYỂN PHÒNG ---
            elif cmd == 'join_room':
                new_room = data['room_name']
                
                # Thông báo rời phòng cũ
                broadcast({"type": "info", "msg": f"{my_name} đã rời phòng."}, room_name=current_room)
                
                # Cập nhật phòng mới
                clients[client_socket]['room'] = new_room
                
                # Thông báo vào phòng mới
                send_json(client_socket, {"type": "info", "msg": f"Bạn đã chuyển sang phòng: {new_room}"})
                broadcast({"type": "info", "msg": f"{my_name} đã tham gia phòng."}, room_name=new_room)

            # --- XỬ LÝ CHAT RIÊNG (Private) ---
            elif cmd == 'private_msg':
                recipient = data['recipient']
                content = data['msg']
                found = False
                
                for sock, info in clients.items():
                    if info['nick'] == recipient:
                        # Gửi cho người nhận
                        send_json(sock, {"type": "private", "sender": my_name, "msg": content})
                        # Gửi lại cho người gửi (để họ biết đã gửi thành công)
                        send_json(client_socket, {"type": "info", "msg": f"[Mật] Tới {recipient}: {content}"})
                        found = True
                        break
                
                if not found:
                    send_json(client_socket, {"type": "error", "msg": f"Không tìm thấy người dùng '{recipient}'"})

            # --- XỬ LÝ XEM DANH SÁCH ---
            elif cmd == 'list_users':
                # Lọc ra danh sách người trong cùng phòng
                users = [info['nick'] for sock, info in clients.items() if info['room'] == current_room]
                list_str = ", ".join(users)
                send_json(client_socket, {"type": "info", "msg": f"Danh sách trong {current_room}: {list_str}"})

    except:
        pass
    finally:
        if client_socket in clients:
            info = clients[client_socket]
            del clients[client_socket]
            broadcast({"type": "info", "msg": f"{info['nick']} đã thoát."}, room_name=info['room'])
            print(f"[Thoát] {info['nick']} đã rời server.")
        client_socket.close()

# --- MAIN ---
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
print(f"Server v2 (Rooms & Private) đang chạy trên {HOST}:{PORT}")

while True:
    client, addr = server.accept()
    t = threading.Thread(target=handle_client, args=(client,))
    t.start()
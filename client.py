import socket
import threading
import json
import struct
import sys

# --- CẤU HÌNH KẾT NỐI ---
HOST = 'learn-if.gl.at.ply.gg'  
PORT = 60326

# --- CÁC HÀM HỖ TRỢ (GIỮ NGUYÊN) ---
def send_json(sock, data):
    try:
        json_data = json.dumps(data).encode('utf-8')
        msg_len = struct.pack('!I', len(json_data))
        sock.sendall(msg_len + json_data)
    except:
        pass

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

# --- LOGIC CLIENT (NÂNG CẤP HIỂN THỊ & NHẬP LỆNH) ---
def receive_messages(client_socket):
    while True:
        try:
            data = recv_json(client_socket)
            if not data:
                print("\n[!] Mất kết nối.")
                client_socket.close()
                sys.exit() # Thoát chương trình luôn
            
            dtype = data.get('type')
            
            if dtype == 'chat':
                print(f"\n[{data['room']}] {data['sender']}: {data['msg']}")
            elif dtype == 'private':
                print(f"\n>>> [MẬT] Từ {data['sender']}: {data['msg']}")
            elif dtype == 'info':
                print(f"\n>>> [HỆ THỐNG]: {data['msg']}")
            elif dtype == 'error':
                print(f"\n>>> [LỖI]: {data['msg']}")
                
        except:
            break

def send_messages(client_socket):
    while True:
        try:
            msg = input("")
            if not msg: continue

            # --- XỬ LÝ CÁC LỆNH ĐẶC BIỆT ---
            if msg.lower() == '/quit':
                client_socket.close()
                sys.exit()
            
            elif msg.lower() == '/help':
                print("\n--- HƯỚNG DẪN SỬ DỤNG ---")
                print("/join <TênPhòng>  : Chuyển sang phòng khác")
                print("/dm <Tên> <Tin>   : Nhắn tin riêng (Mật)")
                print("/list             : Xem ai đang ở trong phòng")
                print("/quit             : Thoát")
                print("-------------------------")

            elif msg.lower().startswith('/join '):
                # Cắt chuỗi lấy tên phòng. VD: "/join Game" -> "Game"
                parts = msg.split(" ", 1)
                if len(parts) > 1:
                    send_json(client_socket, {"type": "join_room", "room_name": parts[1]})
                else:
                    print(">>> Lỗi: Vui lòng nhập tên phòng. VD: /join Game")

            elif msg.lower().startswith('/dm '):
                # Cắt chuỗi lấy tên và tin. VD: "/dm Bob Alo ban oi"
                parts = msg.split(" ", 2)
                if len(parts) == 3:
                    send_json(client_socket, {"type": "private_msg", "recipient": parts[1], "msg": parts[2]})
                else:
                    print(">>> Lỗi: Sai cú pháp. Dùng: /dm <Tên> <Nội dung>")

            elif msg.lower() == '/list':
                send_json(client_socket, {"type": "list_users"})

            else:
                # Nếu không phải lệnh, gửi như tin nhắn chat thường
                send_json(client_socket, {"type": "chat", "msg": msg})

        except:
            break

# --- MAIN ---
print("--- CHAT APP v2 (Rooms & Private) ---")
print("Gõ /help để xem danh sách lệnh.")
nickname = input("Nhập tên của bạn: ")

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    print(f"Đang kết nối đến {HOST}:{PORT}...")
    client.connect((HOST, PORT))
    send_json(client, {"type": "login", "nickname": nickname})
except Exception as e:
    print(f"Không thể kết nối: {e}")
    sys.exit()

recv_thread = threading.Thread(target=receive_messages, args=(client,))
recv_thread.daemon = True
recv_thread.start()

send_messages(client)

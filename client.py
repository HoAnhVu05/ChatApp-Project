import socket
import threading
import json
import struct
import sys

# --- CẤU HÌNH KẾT NỐI (PLAYIT CỐ ĐỊNH) ---
HOST = 'learn-if.gl.at.ply.gg'  
PORT = 60326

# --- CÁC HÀM HỖ TRỢ (PHẢI GIỐNG SERVER Y HỆT) ---
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

# --- LOGIC CLIENT ---
def receive_messages(client_socket):
    while True:
        try:
            # Nhận gói tin JSON
            data = recv_json(client_socket)
            if not data:
                print("\n[!] Mất kết nối với server.")
                client_socket.close()
                break
            
            # Xử lý hiển thị dựa trên loại tin nhắn
            dtype = data.get('type')
            
            if dtype == 'chat':
                print(f"\n{data['sender']}: {data['msg']}")
            elif dtype == 'info':
                print(f"\n[HỆ THỐNG]: {data['msg']}")
                
        except:
            client_socket.close()
            break

def send_messages(client_socket):
    while True:
        try:
            msg = input("")
            if not msg: continue

            if msg.lower() == '/quit':
                client_socket.close()
                sys.exit()
            
            # Gửi tin nhắn thường dưới dạng JSON
            send_json(client_socket, {"type": "chat", "msg": msg})

        except:
            break

# --- MAIN ---
print("--- CHAT APP V2 (JSON FIX) ---")
nickname = input("Nhập tên của bạn: ")

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    print(f"Đang kết nối đến {HOST}:{PORT}...")
    client.connect((HOST, PORT))
    # Gửi gói tin đăng nhập
    send_json(client, {"type": "login", "nickname": nickname})
except Exception as e:
    print(f"Không thể kết nối: {e}")
    sys.exit()

# Chạy luồng nhận tin
recv_thread = threading.Thread(target=receive_messages, args=(client,))
recv_thread.daemon = True
recv_thread.start()

# Chạy luồng gửi tin
send_messages(client)
import socket
import threading
import json
import struct # Thư viện dùng để đóng gói độ dài tin nhắn (Fix lỗi 1000 ký tự)

HOST = '127.0.0.1'
PORT = 9999

# --- CÁC HÀM HỖ TRỢ (CORE FIX LỖI GÓI TIN) ---
def send_json(sock, data):
    """
    Gửi dữ liệu JSON kèm theo độ dài (Fix lỗi dính gói/cắt gói).
    Quy tắc: [4 byte độ dài][Nội dung JSON]
    """
    try:
        json_data = json.dumps(data).encode('utf-8')
        # Đóng gói độ dài tin nhắn vào 4 byte (Big Endian)
        msg_len = struct.pack('!I', len(json_data))
        sock.sendall(msg_len + json_data)
    except Exception as e:
        print(f"Lỗi gửi JSON: {e}")

def recv_json(sock):
    """
    Nhận dữ liệu JSON dựa trên độ dài gói tin.
    Đảm bảo nhận ĐỦ dữ liệu rồi mới xử lý.
    """
    def recvall(n):
        # Hàm phụ: Nhận đủ n byte mới thôi
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet: return None
            data += packet
        return data

    try:
        # Bước 1: Nhận 4 byte đầu tiên để biết độ dài tin nhắn sắp tới
        raw_msglen = recvall(4)
        if not raw_msglen: return None
        msglen = struct.unpack('!I', raw_msglen)[0]

        # Bước 2: Nhận đủ số byte nội dung dựa trên độ dài đã biết
        raw_data = recvall(msglen)
        if not raw_data: return None
        
        return json.loads(raw_data.decode('utf-8'))
    except Exception as e:
        return None

# --- LOGIC SERVER ---
clients = {} # Lưu socket: nickname

def broadcast(message_dict, exclude_socket=None):
    """Gửi tin nhắn JSON cho tất cả client"""
    for client_socket in list(clients.keys()):
        if client_socket != exclude_socket:
            send_json(client_socket, message_dict)

def handle_client(client_socket):
    try:
        # 1. Nhận yêu cầu Login (Gói tin đầu tiên)
        data = recv_json(client_socket)
        if not data or data['type'] != 'login':
            return
        
        nickname = data['nickname']
        clients[client_socket] = nickname
        
        print(f"[Kết nối] {nickname} đã tham gia.")
        # Gửi thông báo cho mọi người
        broadcast({"type": "info", "msg": f"{nickname} đã tham gia phòng chat!"})

        # 2. Vòng lặp nhận tin nhắn chat
        while True:
            data = recv_json(client_socket)
            if not data: break # Client ngắt kết nối

            if data['type'] == 'chat':
                content = data['msg']
                print(f"{nickname}: {content}")
                # Gửi lại cho các client khác với cấu trúc JSON
                broadcast({
                    "type": "chat", 
                    "sender": nickname, 
                    "msg": content
                }, exclude_socket=client_socket)

    except:
        pass
    finally:
        # Xử lý khi thoát
        if client_socket in clients:
            nick = clients[client_socket]
            del clients[client_socket]
            broadcast({"type": "info", "msg": f"{nick} đã thoát."})
            print(f"[Thoát] {nick} đã rời server.")
        client_socket.close()

# --- MAIN ---
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()

print(f"Server (JSON Mode) đang chạy trên {HOST}:{PORT}")

while True:
    client, addr = server.accept()
    print(f"Có kết nối từ: {addr}")
    t = threading.Thread(target=handle_client, args=(client,))
    t.start()
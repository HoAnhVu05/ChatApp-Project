import socket
import threading
import json
import struct
import sys
import os
import base64 # Thư viện để mã hóa file thành chuỗi

# --- CẤU HÌNH KẾT NỐI ---
HOST = 'learn-if.gl.at.ply.gg'  # <-- THAY CỦA BẠN
PORT = 60326                    # <-- THAY CỦA BẠN

# Tạo thư mục downloads nếu chưa có
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# --- CÁC HÀM HỖ TRỢ ---
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
            data = recv_json(client_socket)
            if not data:
                print("\n[!] Mất kết nối.")
                client_socket.close()
                sys.exit()
            
            dtype = data.get('type')
            
            if dtype == 'chat':
                print(f"\n[{data['room']}] {data['sender']}: {data['msg']}")
            
            elif dtype == 'private':
                print(f"\n>>> [MẬT] Từ {data['sender']}: {data['msg']}")
            
            elif dtype == 'info':
                print(f"\n>>> [HỆ THỐNG]: {data['msg']}")
            
            elif dtype == 'error':
                print(f"\n>>> [LỖI]: {data['msg']}")
            
            elif dtype == 'file':
                # Xử lý nhận file
                sender = data['sender']
                filename = data['filename']
                file_content = base64.b64decode(data['content']) # Giải mã chuỗi thành byte
                
                # Lưu file
                filepath = os.path.join("downloads", filename)
                with open(filepath, "wb") as f:
                    f.write(file_content)
                
                print(f"\n>>> [FILE] {sender} đã gửi file '{filename}'. Đã lưu tại {filepath}")

        except Exception as e:
            print(e)
            break

def send_messages(client_socket):
    while True:
        try:
            msg = input("")
            if not msg: continue

            if msg.lower() == '/quit':
                client_socket.close()
                sys.exit()
            
            elif msg.lower() == '/help':
                print("\n--- HƯỚNG DẪN ---")
                print("/join <TênPhòng>      : Chuyển phòng")
                print("/dm <Tên> <Tin>       : Nhắn riêng")
                print("/sendfile <ĐườngDẫn>  : Gửi file (VD: /sendfile anh.jpg)")
                print("/list                 : Xem danh sách")
                print("/quit                 : Thoát")
                print("---------------------")

            elif msg.lower().startswith('/join '):
                parts = msg.split(" ", 1)
                if len(parts) > 1:
                    send_json(client_socket, {"type": "join_room", "room_name": parts[1]})

            elif msg.lower().startswith('/dm '):
                parts = msg.split(" ", 2)
                if len(parts) == 3:
                    send_json(client_socket, {"type": "private_msg", "recipient": parts[1], "msg": parts[2]})

            elif msg.lower().startswith('/sendfile '):
                # Cú pháp: /sendfile C:\Users\HinhAnh\avatar.jpg
                file_path = msg.split(" ", 1)[1].replace('"', '') # Xóa dấu ngoặc kép nếu có
                
                if os.path.exists(file_path):
                    # Kiểm tra kích thước file (Giới hạn 5MB cho an toàn)
                    if os.path.getsize(file_path) > 5 * 1024 * 1024:
                        print(">>> Lỗi: File quá lớn (>5MB).")
                        continue

                    print(">>> Đang gửi file...")
                    with open(file_path, "rb") as f:
                        file_data = f.read()
                        # Mã hóa file thành chuỗi base64 để gửi qua JSON
                        encoded_data = base64.b64encode(file_data).decode('utf-8')
                    
                    filename = os.path.basename(file_path)
                    send_json(client_socket, {
                        "type": "file",
                        "filename": filename,
                        "content": encoded_data
                    })
                    print(f">>> Đã gửi file '{filename}' thành công!")
                else:
                    print(">>> Lỗi: Không tìm thấy file.")

            elif msg.lower() == '/list':
                send_json(client_socket, {"type": "list_users"})

            else:
                send_json(client_socket, {"type": "chat", "msg": msg})

        except:
            break

# --- MAIN ---
print("--- CHAT APP v3 (File Transfer) ---")
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
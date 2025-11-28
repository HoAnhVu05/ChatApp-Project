# File: server.py
# Description: Máy chủ chat an toàn sử dụng SSL/TLS

import socket
import threading
import json
import struct
import datetime
import ssl
import os

# --- CẤU HÌNH SERVER ---
HOST = '127.0.0.1'
PORT = 9999
LOG_FILE = "chat_history.log"
CERT_FILE = 'server.crt'
KEY_FILE = 'server.key'

# --- BIẾN TOÀN CỤC & KHÓA ---
# clients: Lưu trữ socket và thông tin của các client đang kết nối
# { client_socket: {"nick": "nickname", "room": "room_name"} }
clients = {}
# clients_lock: Đảm bảo việc truy cập (đọc/ghi) vào dict 'clients' là an toàn trong môi trường đa luồng
clients_lock = threading.Lock()

# --- CÁC HÀM TIỆN ÍCH ---

def save_log(message):
    """Ghi lại một thông điệp kèm timestamp vào file log và in ra console."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
        print(log_message)
    except Exception as e:
        print(f"Lỗi khi ghi log: {e}")

def send_json(sock, data):
    """Mã hóa dữ liệu (dict) thành JSON, đóng gói và gửi đi."""
    try:
        json_data = json.dumps(data).encode('utf-8')
        msg_len = struct.pack('!I', len(json_data))
        sock.sendall(msg_len + json_data)
    except Exception as e:
        # Lỗi này thường xảy ra khi client đã ngắt kết nối
        # save_log(f"Lỗi gửi tin đến {sock.getpeername()}: {e}")
        pass

def recv_json(sock):
    """Nhận, giải mã và trả về dữ liệu JSON từ socket."""
    try:
        # Đọc 4 bytes đầu tiên để biết độ dài của tin nhắn
        raw_msglen = sock.recv(4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('!I', raw_msglen)[0]

        # Nhận đủ dữ liệu dựa trên độ dài đã biết
        data = b''
        while len(data) < msglen:
            packet = sock.recv(msglen - len(data))
            if not packet:
                return None
            data += packet
        
        return json.loads(data.decode('utf-8'))
    except (struct.error, json.JSONDecodeError):
        # Lỗi xảy ra nếu dữ liệu nhận được không hợp lệ
        return None
    except Exception:
        # Các lỗi khác (ví dụ: connection reset)
        return None

# --- XỬ LÝ LOGIC CHÍNH ---

def broadcast(message_dict, room_name=None, exclude_socket=None):
    """Gửi một thông điệp tới tất cả client (hoặc trong một phòng cụ thể)."""
    with clients_lock:
        # Tạo một bản sao của danh sách client để tránh lỗi khi dict thay đổi kích thước
        current_clients = list(clients.items())
    
    for client_socket, info in current_clients:
        if client_socket != exclude_socket:
            if room_name is None or info['room'] == room_name:
                send_json(client_socket, message_dict)

def handle_client(client_socket, client_address):
    """Xử lý toàn bộ logic cho một client: đăng nhập, nhận và xử lý tin nhắn."""
    nickname = None
    try:
        # 1. Xử lý đăng nhập
        login_data = recv_json(client_socket)
        if not login_data or login_data.get('type') != 'login':
            save_log(f"Từ chối kết nối từ {client_address}: Không phải tin nhắn login.")
            return

        nickname = login_data.get('nickname')
        if not nickname:
            save_log(f"Từ chối kết nối từ {client_address}: Nickname rỗng.")
            send_json(client_socket, {"type": "error", "msg": "Tên không được để trống."})
            return

        with clients_lock:
            if any(info['nick'] == nickname for info in clients.values()):
                save_log(f"Từ chối {nickname} từ {client_address}: Tên đã tồn tại.")
                send_json(client_socket, {"type": "error", "msg": f"Tên '{nickname}' đã có người sử dụng."})
                return
            
            # Thêm client vào danh sách
            clients[client_socket] = {"nick": nickname, "room": "Lobby"}

        # Gửi thông báo chào mừng và thông báo cho mọi người
        save_log(f"[KẾT NỐI] {nickname} từ {client_address} đã vào Lobby.")
        send_json(client_socket, {"type": "info", "msg": f"Chào {nickname}! Kết nối đã được MÃ HÓA SSL."})       
        broadcast({"type": "info", "msg": f"{nickname} đã vào phòng."}, "Lobby", client_socket)

        # 2. Vòng lặp xử lý tin nhắn
        while True:
            data = recv_json(client_socket)
            if data is None:
                break # Client đã ngắt kết nối

            try:
                # Lấy thông tin người gửi và phòng hiện tại một cách an toàn
                with clients_lock:
                    if client_socket not in clients: break
                    my_info = clients[client_socket]
                    current_room = my_info['room']
                    my_name = my_info['nick']
                
                cmd = data.get('type')

                # --- Xử lý các loại lệnh ---
                if cmd == 'chat':
                    msg = data.get('msg', '')
                    save_log(f"[{current_room}] {my_name}: {msg}")
                    broadcast({"type": "chat", "sender": my_name, "msg": msg, "room": current_room}, current_room, client_socket)
                
                elif cmd == 'join_room':
                    new_room = data.get('room_name', 'Lobby')
                    broadcast({"type": "info", "msg": f"{my_name} rời phòng."}, current_room, client_socket)
                    with clients_lock:
                        clients[client_socket]['room'] = new_room
                    send_json(client_socket, {"type": "info", "msg": f"Đã vào phòng: {new_room}"})
                    broadcast({"type": "info", "msg": f"{my_name} vào phòng."}, new_room, client_socket)

                elif cmd == 'private_msg':
                    recipient = data.get('recipient')
                    msg = data.get('msg')
                    if not recipient or not msg:
                        send_json(client_socket, {"type": "error", "msg": "Thiếu thông tin. Sử dụng: /dm \"<Tên>\" <TinNhắn>"})
                        continue
                    
                    recipient_socket = None
                    with clients_lock:
                        for sock, info in clients.items():
                            if info['nick'] == recipient:
                                recipient_socket = sock
                                break
                    
                    if recipient_socket:
                        send_json(recipient_socket, {"type": "private", "sender": my_name, "msg": msg})
                        send_json(client_socket, {"type": "info", "msg": f"[Mật] Đã gửi tin nhắn tới {recipient}."})
                    else:
                        send_json(client_socket, {"type": "error", "msg": f"Không tìm thấy người dùng '{recipient}'."})

                elif cmd == 'list_users':
                    with clients_lock:
                        users_in_room = [info['nick'] for info in clients.values() if info['room'] == current_room]
                    send_json(client_socket, {"type": "info", "msg": f"Thành viên trong {current_room}: {', '.join(users_in_room) if users_in_room else '(không có ai)'}"})

                elif cmd == 'list_all_users':
                    # Trả về danh sách tất cả thành viên trong server với thông tin phòng
                    with clients_lock:
                        users_by_room = {}
                        for info in clients.values():
                            room = info['room']
                            nick = info['nick']
                            if room not in users_by_room:
                                users_by_room[room] = []
                            users_by_room[room].append(nick)
                        
                        if users_by_room:
                            # Gửi từng dòng riêng để hiển thị đẹp hơn
                            send_json(client_socket, {"type": "info", "msg": "=== TẤT CẢ THÀNH VIÊN TRONG SERVER ==="})
                            for room in sorted(users_by_room.keys()):
                                users = users_by_room[room]
                                send_json(client_socket, {"type": "info", "msg": f"  [{room}]: {', '.join(users)}"})
                            send_json(client_socket, {"type": "info", "msg": "====================================="})
                        else:
                            send_json(client_socket, {"type": "info", "msg": "Không có thành viên nào trong server."})

                elif cmd == 'list_rooms':
                    # Trả về danh sách các phòng hiện có (unique)
                    with clients_lock:
                        rooms = sorted({info['room'] for info in clients.values()})
                    send_json(client_socket, {"type": "rooms", "rooms": rooms})

                elif cmd == 'file':
                    filename = data.get('filename', 'unknown')
                    save_log(f"[FILE] {my_name} gửi file '{filename}' trong phòng {current_room}.")
                    broadcast(data, current_room, client_socket)
                    send_json(client_socket, {"type": "info", "msg": f"Đã gửi file '{filename}' tới tất cả thành viên trong phòng {current_room}."})

                elif cmd == 'private_file':
                    recipient = data.get('recipient')
                    filename = data.get('filename')
                    if not recipient or not filename:
                        send_json(client_socket, {"type": "error", "msg": "Thiếu thông tin. Sử dụng: /senddmfile \"<Tên>\" \"<ĐườngDẫn>\""})
                        continue
                    
                    recipient_socket = None
                    with clients_lock:
                        for sock, info in clients.items():
                            if info['nick'] == recipient:
                                recipient_socket = sock
                                break
                    
                    if recipient_socket:
                        save_log(f"[FILE RIÊNG] {my_name} gửi file riêng cho {recipient}.")
                        send_json(recipient_socket, {
                            "type": "private_file",
                            "sender": my_name,
                            "filename": filename,
                            "content": data.get('content', '')
                        })
                        send_json(client_socket, {"type": "info", "msg": f"[Mật] Đã gửi file '{filename}' cho {recipient}."})
                    else:
                        send_json(client_socket, {"type": "error", "msg": f"Không tìm thấy người dùng '{recipient}'."})

                elif cmd == 'ping':
                    send_json(client_socket, {"type": "pong"})

            except KeyError as e:
                save_log(f"Lỗi dữ liệu không hợp lệ từ {nickname}: Thiếu key {e}")
            except Exception as e:
                save_log(f"Lỗi khi xử lý tin nhắn từ {nickname}: {e}")

    except Exception as e:
        save_log(f"Lỗi nghiêm trọng với client {client_address} ({nickname}): {e}")
    finally:
        # 3. Dọn dẹp khi client thoát
        with clients_lock:
            if client_socket in clients:
                info = clients.pop(client_socket)
                nickname = info.get('nick', 'Một người dùng')
                room = info.get('room', 'Lobby')
                save_log(f"[NGẮT KẾT NỐI] {nickname} đã thoát.")
                broadcast({"type": "info", "msg": f"{nickname} đã rời phòng."}, room)
        client_socket.close()


def main():
    """Khởi tạo và chạy server."""
    # 1. Kiểm tra file certificate
    if not (os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)):
        save_log(f"LỖI: Không tìm thấy {CERT_FILE} hoặc {KEY_FILE}. Hãy chạy 'py gen_cert.py' trước.")
        return

    # 2. Cấu hình SSL context
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    # Hiển thị thông báo rằng server đã nạp chứng chỉ và sẽ chạy ở chế độ SSL/TLS
    save_log(f"--- SERVER SECURE (SSL/TLS) ĐANG SẴN SÀNG TRÊN {HOST}:{PORT} (cert loaded) ---")

    # 3. Khởi tạo socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
    except OSError:
        save_log(f"LỖI: Cổng {PORT} đang được sử dụng. Hãy đóng ứng dụng khác hoặc đổi cổng.")
        return
    
    server_socket.listen()
    save_log(f"--- SERVER CHAT AN TOÀN ĐANG CHẠY TRÊN {HOST}:{PORT} ---")

    # 4. Vòng lặp chấp nhận kết nối
    while True:
        try:
            client_raw, addr = server_socket.accept()
            save_log(f"Chấp nhận kết nối thô từ {addr}...")
            
            # Nâng cấp kết nối lên SSL
            client_ssl = context.wrap_socket(client_raw, server_side=True)
            
            # Tạo một luồng mới để xử lý client
            thread = threading.Thread(target=handle_client, args=(client_ssl, addr))
            thread.daemon = True
            thread.start()

        except ssl.SSLError as e:
            save_log(f"Lỗi SSL Handshake từ {addr}: {e}. Có thể do client kết nối không dùng SSL.")
            if 'client_raw' in locals(): client_raw.close()
        except Exception as e:
            save_log(f"Lỗi khi chấp nhận kết nối: {e}")

if __name__ == "__main__":
    main()

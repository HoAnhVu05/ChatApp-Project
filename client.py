# File: client.py
# Description: Máy khách chat an toàn sử dụng SSL/TLS

import socket
import threading
import json
import struct
import sys
import os
import base64
import ssl
import time

# --- CẤU HÌNH ---
# THAY ĐỔI ĐỊA CHỈ VÀ CỔNG MÀ BẠN CÓ (ví dụ: từ playit.gg)
HOST = 'learn-if.gl.at.ply.gg' # Mặc định là máy local, thay bằng địa chỉ public của bạn
PORT = 60326          # Thay bằng cổng public của bạn

DOWNLOAD_DIR = "downloads"

# --- LỚP CHAT CLIENT ---

class ChatClient:
    """Quản lý toàn bộ logic cho một client chat."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.client_socket = None
        self.nickname = ""
        # Cờ để báo hiệu cho các luồng dừng lại
        self.shutdown_event = threading.Event()

    def _send_json(self, data):
        """Mã hóa và gửi dữ liệu JSON một cách an toàn."""
        if self.shutdown_event.is_set(): return
        try:
            json_data = json.dumps(data).encode('utf-8')
            msg_len = struct.pack('!I', len(json_data))
            self.client_socket.sendall(msg_len + json_data)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.handle_disconnect()
        except Exception as e:
            print(f"\n[Lỗi] Không thể gửi tin nhắn: {e}")

    def _recv_json(self):
        """Nhận và giải mã dữ liệu JSON."""
        try:
            raw_msglen = self.client_socket.recv(4)
            if not raw_msglen: return None
            msglen = struct.unpack('!I', raw_msglen)[0]

            data = b''
            while len(data) < msglen:
                packet = self.client_socket.recv(msglen - len(data))
                if not packet: return None
                data += packet
            
            return json.loads(data.decode('utf-8'))
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            return None # Server đã ngắt kết nối
        except (struct.error, json.JSONDecodeError):
            print("\n[Lỗi] Nhận được dữ liệu không hợp lệ từ server.")
            return None
        except Exception:
            return None
            
    def handle_disconnect(self):
        """Xử lý khi mất kết nối tới server."""
        if not self.shutdown_event.is_set():
            print("\n[!] Mất kết nối tới server. Vui lòng khởi động lại ứng dụng.")
            self.shutdown_event.set() # Báo hiệu cho các luồng khác dừng lại

    def _receive_loop(self):
        """Vòng lặp lắng nghe tin nhắn từ server."""
        while not self.shutdown_event.is_set():
            data = self._recv_json()
            if data is None:
                self.handle_disconnect()
                break

            try:
                dtype = data.get('type')
                # In một dòng trống để không ghi đè lên input của người dùng
                sys.stdout.write('\r' + ' ' * 60 + '\r')
                
                if dtype == 'chat':
                    print(f"[{data.get('room', 'Unknown')}] {data.get('sender', 'System')}: {data.get('msg', '')}")
                elif dtype == 'private':
                    print(f">>> [MẬT] Từ {data.get('sender', 'System')}: {data.get('msg', '')}")
                elif dtype == 'info':
                    print(f">>> [HỆ THỐNG]: {data.get('msg', '')}")
                elif dtype == 'error':
                    print(f">>> [LỖI]: {data.get('msg', '')}")
                    if "Tên" in data.get('msg', ''): # Nếu lỗi do trùng tên -> thoát
                        self.shutdown_event.set()
                elif dtype == 'rooms':
                    rooms = data.get('rooms', [])
                    print(f"\n>>> [PHÒNG HIỆN CÓ]: {', '.join(rooms) if rooms else '(không có phòng nào)'}")
                elif dtype == 'pong':
                    continue # Bỏ qua, chỉ dùng để giữ kết nối
                elif dtype == 'file':
                    self._save_file(data)
                
                # In lại tên người dùng để họ tiếp tục gõ
                sys.stdout.write(f"{self.nickname}> ")
                sys.stdout.flush()

            except Exception as e:
                print(f"\n[Lỗi] Xảy ra lỗi khi xử lý tin nhắn: {e}")

    def _save_file(self, data):
        """Lưu file nhận được từ server."""
        try:
            filename = data.get('filename')
            sender = data.get('sender', 'System')
            if not filename: return
            
            file_content = base64.b64decode(data.get('content', ''))
            filepath = os.path.join(DOWNLOAD_DIR, os.path.basename(filename)) # os.path.basename để bảo mật
            
            with open(filepath, "wb") as f:
                f.write(file_content)
            print(f">>> [FILE] {sender} đã gửi '{filename}'. Đã lưu vào thư mục '{DOWNLOAD_DIR}'.")
        except Exception as e:
            print(f"\n[Lỗi] Không thể lưu file '{filename}': {e}")
            
    def _ping_loop(self):
        """Vòng lặp gửi ping để giữ kết nối."""
        while not self.shutdown_event.is_set():
            self._send_json({"type": "ping"})
            # Dùng is_set() với timeout để luồng có thể dừng nhanh hơn
            self.shutdown_event.wait(30) 

    def _handle_user_input(self, msg):
        """Phân tích và xử lý input từ người dùng."""
        if msg.startswith('/'):
            parts = msg.split(" ", 2)
            command = parts[0].lower()

            if command == '/quit':
                self.shutdown_event.set()
            elif command == '/help':
                print("\n--- HƯỚNG DẪN (SECURE CHAT) ---\
""/join <TênPhòng>      : Chuyển phòng\n""/dm <Tên> <TinNhắn>   : Nhắn tin riêng\n""/sendfile <ĐườngDẫn>  : Gửi file cho mọi người trong phòng\n""/list                 : Xem danh sách người dùng trong phòng\n""/rooms                : Xem danh sách phòng hiện có\n""/quit                 : Thoát chương trình\n""-------------------------------")
            elif command == '/join':
                if len(parts) > 1: self._send_json({"type": "join_room", "room_name": parts[1]})
                else: print("Sử dụng: /join <TênPhòng>")
            elif command == '/dm':
                if len(parts) == 3: self._send_json({"type": "private_msg", "recipient": parts[1], "msg": parts[2]})
                else: print("Sử dụng: /dm <TênNgườiNhận> <TinNhắn>")
            elif command == '/list':
                self._send_json({"type": "list_users"})
            elif command == '/rooms':
                self._send_json({"type": "list_rooms"})
            elif command == '/sendfile':
                if len(parts) > 1: self._send_file(parts[1])
                else: print("Sử dụng: /sendfile <ĐườngDẫnTớiFile>")
            else:
                print(f"Lệnh '{command}' không hợp lệ. Gõ /help để xem danh sách lệnh.")
        else:
            # Tin nhắn chat thông thường
            self._send_json({"type": "chat", "msg": msg})

    def _send_file(self, file_path):
        """Đọc, mã hóa và gửi file."""
        file_path = file_path.strip('"')
        if not os.path.exists(file_path):
            print(f">>> Lỗi: File '{file_path}' không tồn tại.")
            return
        if os.path.getsize(file_path) > 10 * 1024 * 1024: # Giới hạn 10MB
            print(">>> Lỗi: File quá lớn (tối đa 10MB).")
            return
            
        print(">>> Đang mã hóa và gửi file...")
        try:
            with open(file_path, "rb") as f:
                encoded_data = base64.b64encode(f.read()).decode('utf-8')
            filename = os.path.basename(file_path)
            self._send_json({"type": "file", "filename": filename, "content": encoded_data})
            print(">>> Đã gửi file thành công.")
        except Exception as e:
            print(f">>> Lỗi khi đọc file: {e}")

    def start(self):
        """Khởi động client, kết nối và bắt đầu các luồng."""
        # 1. Nhập nickname
        while not self.nickname:
            self.nickname = input("Nhập tên của bạn: ").strip()

        # 2. Tạo thư mục download nếu chưa có
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)

        # 3. Cấu hình và kết nối SSL
        context = ssl.create_default_context()
        context.check_hostname = False # Tắt kiểm tra hostname vì dùng cert tự ký
        context.verify_mode = ssl.CERT_NONE  # Không xác thực cert từ server

        try:
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket = context.wrap_socket(raw_socket, server_hostname=self.host)
            print(f"Đang kết nối tới {self.host}:{self.port}...")
            self.client_socket.connect((self.host, self.port))
        except Exception as e:
            print(f"Không thể kết nối tới server: {e}")
            return

        # 4. Gửi thông tin đăng nhập
        self._send_json({"type": "login", "nickname": self.nickname})

        # 5. Khởi chạy các luồng
        threading.Thread(target=self._receive_loop, daemon=True).start()
        threading.Thread(target=self._ping_loop, daemon=True).start()
        
        # 6. Vòng lặp nhận input từ người dùng
        print(f"--- CHÀO MỪNG {self.nickname} ĐẾN VỚI SECURE CHAT --- (gõ /help để xem hướng dẫn)")
        while not self.shutdown_event.is_set():
            try:
                msg = input(f"{self.nickname}> ")
                if msg:
                    self._handle_user_input(msg)
            except (KeyboardInterrupt, EOFError):
                self.shutdown_event.set()
            except Exception as e:
                print(f"Lỗi nhập liệu: {e}")
        
        print("\nĐang đóng kết nối...")
        self.client_socket.close()

def main():
    """Hàm chính để chạy client."""
    client = ChatClient(HOST, PORT)
    client.start()
    print("Chương trình đã thoát.")

if __name__ == "__main__":
    main()

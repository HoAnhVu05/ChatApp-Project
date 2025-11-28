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
        # Cờ để đánh dấu đã sẵn sàng nhận input
        self.ready_for_input = threading.Event()

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
                
                # Xóa dòng input hiện tại (nếu có) để in tin nhắn
                sys.stdout.write('\r' + ' ' * 80 + '\r')
                
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
                    print(f">>> [PHÒNG HIỆN CÓ]: {', '.join(rooms) if rooms else '(không có phòng nào)'}")
                elif dtype == 'pong':
                    continue # Bỏ qua, chỉ dùng để giữ kết nối
                elif dtype == 'file':
                    self._save_file(data)
                elif dtype == 'private_file':
                    sender = data.get('sender', 'System')
                    print(f">>> [FILE RIÊNG] {sender} đã gửi file riêng cho bạn.")
                    self._save_file(data)
                
                # In lại prompt để người dùng tiếp tục gõ (chỉ khi đã sẵn sàng)
                if self.ready_for_input.is_set():
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

    def _parse_dm_command(self, msg):
        """Parse lệnh /dm với hỗ trợ tên có nhiều từ (có thể dùng dấu ngoặc kép)."""
        # Bỏ phần lệnh
        content = msg[3:].strip()  # Bỏ "/dm"
        
        if not content:
            return None, None
        
        # Kiểm tra nếu có dấu ngoặc kép ở đầu (tên có nhiều từ)
        if content.startswith('"'):
            # Tìm dấu ngoặc kép đóng đầu tiên
            end_quote = content.find('"', 1)
            if end_quote > 0:
                recipient = content[1:end_quote]
                message = content[end_quote + 1:].strip()
                if message:
                    return recipient, message
        elif content.startswith("'"):
            # Tìm dấu ngoặc kép đơn đóng đầu tiên
            end_quote = content.find("'", 1)
            if end_quote > 0:
                recipient = content[1:end_quote]
                message = content[end_quote + 1:].strip()
                if message:
                    return recipient, message
        else:
            # Không có dấu ngoặc kép, parse bình thường: từ đầu tiên là recipient, phần còn lại là message
            parts = content.split(None, 1)  # Chia thành 2 phần: recipient và message
            if len(parts) == 2:
                return parts[0], parts[1]
        
        return None, None
    
    def _parse_senddmfile_command(self, msg):
        """Parse lệnh /senddmfile với hỗ trợ tên và đường dẫn có nhiều từ."""
        # Bỏ phần lệnh
        content = msg[12:].strip()  # Bỏ "/senddmfile"
        
        if not content:
            return None, None
        
        recipient = None
        file_path = None
        
        # Parse recipient (có thể có dấu ngoặc kép hoặc không)
        if content.startswith('"'):
            end_quote = content.find('"', 1)
            if end_quote > 0:
                recipient = content[1:end_quote]
                content = content[end_quote + 1:].strip()
        elif content.startswith("'"):
            end_quote = content.find("'", 1)
            if end_quote > 0:
                recipient = content[1:end_quote]
                content = content[end_quote + 1:].strip()
        else:
            # Không có dấu ngoặc kép, từ đầu tiên là recipient
            parts = content.split(None, 1)
            if len(parts) >= 1:
                recipient = parts[0]
                if len(parts) > 1:
                    content = parts[1].strip()
                else:
                    content = ""
        
        if not recipient:
            return None, None
        
        # Parse file_path (phần còn lại, có thể có dấu ngoặc kép)
        if content:
            file_path = content.strip('"\'')
        
        if recipient and file_path:
            return recipient, file_path
        
        return None, None

    def _handle_user_input(self, msg):
        """Phân tích và xử lý input từ người dùng."""
        if msg.startswith('/'):
            parts = msg.split(" ", 1)
            command = parts[0].lower()

            if command == '/quit':
                self.shutdown_event.set()
            elif command == '/help':
                print("\n--- HƯỚNG DẪN (SECURE CHAT) ---")
                print("/join <TênPhòng>           : Chuyển phòng")
                print("/dm \"<Tên>\" <TinNhắn>      : Nhắn tin riêng (dùng \"\" nếu tên có nhiều từ)")
                print("/sendfile <ĐườngDẫn>       : Gửi file cho mọi người trong phòng")
                print("/senddmfile \"<Tên>\" \"<ĐườngDẫn>\" : Gửi file riêng (dùng \"\" nếu có khoảng trắng)")
                print("/list                      : Xem danh sách người dùng trong phòng")
                print("/listserver                : Xem tất cả thành viên trong server (tất cả phòng)")
                print("/rooms                     : Xem danh sách phòng hiện có")
                print("/quit                      : Thoát chương trình")
                print("\nLưu ý: Trong terminal Windows, dán (paste) dùng Ctrl+Shift+V hoặc chuột phải")
                print("-------------------------------")
            elif command == '/join':
                if len(parts) > 1:
                    room_name = parts[1].strip().strip('"\'')
                    self._send_json({"type": "join_room", "room_name": room_name})
                else:
                    print("Sử dụng: /join <TênPhòng>")
            elif command == '/dm':
                recipient, message = self._parse_dm_command(msg)
                if recipient and message:
                    self._send_json({"type": "private_msg", "recipient": recipient, "msg": message})
                else:
                    print("Sử dụng: /dm \"<TênNgườiNhận>\" <TinNhắn>")
                    print("Ví dụ: /dm \"Con Chim\" Chào bạn")
            elif command == '/list':
                self._send_json({"type": "list_users"})
            elif command == '/listserver':
                self._send_json({"type": "list_all_users"})
            elif command == '/rooms':
                self._send_json({"type": "list_rooms"})
            elif command == '/sendfile':
                if len(parts) > 1:
                    file_path = parts[1].strip().strip('"\'')
                    self._send_file(file_path)
                else:
                    print("Sử dụng: /sendfile <ĐườngDẫnTớiFile>")
            elif command == '/senddmfile':
                recipient, file_path = self._parse_senddmfile_command(msg)
                if recipient and file_path:
                    self._send_file_private(recipient, file_path)
                else:
                    print("Sử dụng: /senddmfile \"<TênNgườiNhận>\" \"<ĐườngDẫnTớiFile>\"")
                    print("Ví dụ: /senddmfile \"Con Chim\" \"C:\\Users\\file.txt\"")
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
        
        print(">>> Đang mã hóa và gửi file...")
        try:
            # Kiểm tra kích thước file trước
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # Giới hạn 10MB
                print(">>> Lỗi: File quá lớn (tối đa 10MB).")
                return
            
            with open(file_path, "rb") as f:
                file_data = f.read()
            
            # Mã hóa file
            encoded_data = base64.b64encode(file_data).decode('utf-8')
            filename = os.path.basename(file_path)
            
            # Kiểm tra kích thước sau khi encode (base64 tăng ~33%)
            if len(encoded_data) > 15 * 1024 * 1024:  # ~13.3MB base64
                print(">>> Lỗi: File quá lớn sau khi mã hóa.")
                return
            
            self._send_json({"type": "file", "filename": filename, "content": encoded_data})
            print(">>> Đã gửi file thành công.")
        except PermissionError:
            print(f">>> Lỗi: Không có quyền đọc file '{file_path}'.")
        except MemoryError:
            print(f">>> Lỗi: File quá lớn, không đủ bộ nhớ để xử lý.")
        except Exception as e:
            print(f">>> Lỗi khi đọc/ghi file: {e}")
            print(">>> Vui lòng thử lại hoặc kiểm tra file.")

    def _send_file_private(self, recipient, file_path):
        """Đọc, mã hóa và gửi file riêng cho một người."""
        file_path = file_path.strip('"')
        if not os.path.exists(file_path):
            print(f">>> Lỗi: File '{file_path}' không tồn tại.")
            return
        
        print(f">>> Đang mã hóa và gửi file riêng cho {recipient}...")
        try:
            # Kiểm tra kích thước file trước
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # Giới hạn 10MB
                print(">>> Lỗi: File quá lớn (tối đa 10MB).")
                return
            
            with open(file_path, "rb") as f:
                file_data = f.read()
            
            # Mã hóa file
            encoded_data = base64.b64encode(file_data).decode('utf-8')
            filename = os.path.basename(file_path)
            
            # Kiểm tra kích thước sau khi encode
            if len(encoded_data) > 15 * 1024 * 1024:  # ~13.3MB base64
                print(">>> Lỗi: File quá lớn sau khi mã hóa.")
                return
            
            self._send_json({"type": "private_file", "recipient": recipient, "filename": filename, "content": encoded_data})
            print(f">>> Đã gửi file riêng cho {recipient} thành công.")
        except PermissionError:
            print(f">>> Lỗi: Không có quyền đọc file '{file_path}'.")
        except MemoryError:
            print(f">>> Lỗi: File quá lớn, không đủ bộ nhớ để xử lý.")
        except Exception as e:
            print(f">>> Lỗi khi đọc/ghi file: {e}")
            print(">>> Vui lòng thử lại hoặc kiểm tra file.")

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
        
        # 6. Đợi một chút để nhận các tin nhắn ban đầu từ server
        time.sleep(1.0)  # Đợi để server gửi thông báo SSL và các thông báo khác
        
        # 7. Đánh dấu sẵn sàng nhận input và bắt đầu vòng lặp
        self.ready_for_input.set()
        print(f"\n--- CHÀO MỪNG {self.nickname} ĐẾN VỚI SECURE CHAT --- (gõ /help để xem hướng dẫn)")
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

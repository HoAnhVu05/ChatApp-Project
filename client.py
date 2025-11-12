import socket
import threading

def receive_messages(client_socket):
    """Luồng để nhận tin nhắn từ server."""
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
            
            parts = message.split(":", 1)
            command = parts[0]

            if command == "MSG":
                msg_parts = parts[1].split(":", 1)
                sender = msg_parts[0]
                content = msg_parts[1]
                print(f"\n[Tin nhắn từ {sender}]: {content}")
            elif command == "LIST_RSP":
                users = parts[1].split(",")
                print("\n[Danh sách người dùng online]:")
                for user in users:
                    print(f"- {user}")
            elif command == "INFO" or command == "ERROR":
                print(f"\n[SERVER]: {parts[1]}")

        except:
            print("Mất kết nối với server.")
            client_socket.close()
            break

def send_messages(client_socket):
    """Tân Sửa: Luồng để gửi lệnh từ người dùng nhé"""
    """Ok Tân"""
    while True:
        try:
            user_input = input("Nhập lệnh: ")
            
            if user_input.lower() == '/quit':
                client_socket.close()
                break
            
            elif user_input.lower() == '/list':
                client_socket.send(b"LIST:")
                
            elif user_input.startswith('/send '):
                parts = user_input.split(" ", 2)
                if len(parts) < 3:
                    print("Cú pháp sai. Dùng: /send <nickname> <message>")
                    continue
                recipient = parts[1]
                message = parts[2]
                client_socket.send(f"SEND:{recipient}:{message}".encode('utf-8'))
            
            else:
                print("Lệnh không xác định. Các lệnh có sẵn: /list, /send, /quit")
        except:
            print("Kết nối đã đóng.")
            break


# ---- Main ----
# THÔNG TIN KẾT NỐI TỪ NGROK
NGROK_HOST = '0.tcp.ap.ngrok.io'  
NGROK_PORT = 17280          

nickname = input("Nhập nickname của bạn: ")
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    # Sử dụng thông tin của ngrok để kết nối
    print(f"Đang kết nối đến {NGROK_HOST}:{NGROK_PORT}...")
    client.connect((NGROK_HOST, NGROK_PORT))
    client.send(f"LOGIN:{nickname}".encode('utf-8'))
except Exception as e:
    print(f"Không thể kết nối đến server qua ngrok: {e}")
    exit()


print("Đã kết nối. Gõ lệnh để bắt đầu.")
print("Các lệnh: /list, /send <nickname> <message>, /quit")

receive_thread = threading.Thread(target=receive_messages, args=(client,))
receive_thread.start()

send_thread = threading.Thread(target=send_messages, args=(client,))
send_thread.start()
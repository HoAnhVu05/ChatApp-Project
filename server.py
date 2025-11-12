import socket
import threading

HOST = '127.0.0.1'
PORT = 9999

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
print(f"Server đang lắng nghe trên {HOST}:{PORT}")

# Dùng dictionary để lưu client: {nickname: client_socket}
clients = {}

def broadcast(message, _sender_socket=None):
    """Gửi thông báo đến tất cả client, trừ người gửi (nếu có)."""
    for client_socket in clients.values():
        if client_socket != _sender_socket:
            try:
                client_socket.send(message)
            except:
                # Xử lý client đã ngắt kết nối
                pass

def handle_client(client_socket):
    nickname = None
    try:
        # Yêu cầu client đăng nhập
        login_message = client_socket.recv(1024).decode('utf-8')
        if login_message.startswith("LOGIN:"):
            nickname = login_message.split(":")[1]
            if nickname in clients:
                client_socket.send(b"ERROR:Nickname already taken.")
                client_socket.close()
                return
            clients[nickname] = client_socket
            print(f"INFO: {nickname} has joined the chat.")
            broadcast(f"INFO:{nickname} has joined.".encode('utf-8'), client_socket)
        else:
            client_socket.send(b"ERROR:Must login first.")
            client_socket.close()
            return

        # Vòng lặp xử lý các lệnh tiếp theo
        while True:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
            
            print(f"Received from {nickname}: {message}")

            if message.startswith("LIST:"):
                user_list = ",".join(clients.keys())
                client_socket.send(f"LIST_RSP:{user_list}".encode('utf-8'))
            
            elif message.startswith("SEND:"):
                parts = message.split(":", 2)
                recipient = parts[1]
                msg_content = parts[2]
                
                if recipient in clients:
                    recipient_socket = clients[recipient]
                    recipient_socket.send(f"MSG:{nickname}:{msg_content}".encode('utf-8'))
                else:
                    client_socket.send(f"ERROR:User '{recipient}' not found.".encode('utf-8'))
            
            else:
                 client_socket.send(b"ERROR:Unknown command.")

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        # Dọn dẹp khi client ngắt kết nối
        if nickname and nickname in clients:
            del clients[nickname]
            broadcast(f"INFO:{nickname} has left.".encode('utf-s'))
            print(f"INFO: {nickname} has left the chat.")
        client_socket.close()


while True:
    client_socket, address = server.accept()
    print(f"Accepted connection from {address}")
    thread = threading.Thread(target=handle_client, args=(client_socket,))
    thread.start()
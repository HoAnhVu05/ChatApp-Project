import socket, ssl, struct, json, time
HOST='127.0.0.1'
PORT=9999

def send_json(sock, data):
    json_data = json.dumps(data).encode('utf-8')
    sock.sendall(struct.pack('!I', len(json_data)) + json_data)

def recv_json(sock, timeout=5):
    sock.settimeout(timeout)
    try:
        raw = sock.recv(4)
        if not raw:
            return None
        L = struct.unpack('!I', raw)[0]
        data=b''
        while len(data) < L:
            packet = sock.recv(L-len(data))
            if not packet: return None
            data += packet
        return json.loads(data.decode())
    except Exception as e:
        return {'_error': str(e)}

context = ssl.create_default_context()
context.check_hostname=False
context.verify_mode=ssl.CERT_NONE

raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s = context.wrap_socket(raw, server_hostname=HOST)
    s.connect((HOST, PORT))
    print('connected')
    send_json(s, {'type':'login','nickname':'testbot'})
    time.sleep(0.2)
    print('after login recv:', recv_json(s))
    send_json(s, {'type':'list_rooms'})
    time.sleep(0.2)
    print('rooms:', recv_json(s))
    send_json(s, {'type':'join_room','room_name':'Room42'})
    time.sleep(0.2)
    print('after join recv:', recv_json(s))
    send_json(s, {'type':'list_rooms'})
    time.sleep(0.2)
    print('rooms2:', recv_json(s))
except Exception as e:
    print('error:', e)
finally:
    try: s.close()
    except: pass

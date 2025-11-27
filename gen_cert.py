# File: gen_cert.py
# Chạy file này 1 lần duy nhất để tạo server.crt và server.key
from OpenSSL import crypto

def generate_self_signed_cert():
    # 1. Tạo cặp khóa (Private Key)
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)

    # 2. Tạo chứng chỉ (Certificate)
    cert = crypto.X509()
    # Điền thông tin "ảo" cho chứng chỉ
    cert.get_subject().C = "VN"
    cert.get_subject().ST = "Ho Chi Minh"
    cert.get_subject().L = "Thu Duc"
    cert.get_subject().O = "Chat App Project"
    cert.get_subject().OU = "IT Class"
    cert.get_subject().CN = "localhost"
    
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60) # Hạn dùng 10 năm
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')

    # 3. Lưu ra file
    with open("server.crt", "wt") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    with open("server.key", "wt") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))

    print(">>> Đã tạo xong: server.crt và server.key")

if __name__ == "__main__":
    generate_self_signed_cert()
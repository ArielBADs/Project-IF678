import socket
import threading

SERVER_HOST = 'localhost'
SERVER_PORT = 1044
BUFFER_SIZE = 1024
TIMEOUT = 0.2

disconnected = threading.Event()

def rdt_send(sock, data, addr, seq_num):
    while True:
        packet = bytes([seq_num]) + data
        sock.sendto(packet, addr)
        sock.settimeout(TIMEOUT)
        try:
            ack, _ = sock.recvfrom(10)
            ack_msg = ack.decode(errors='ignore').strip()
            if ack_msg == f"ACK{seq_num}":
                return
        except socket.timeout:
            continue

def rdt_recv(sock, expected_seq, server_addr):
    """Recebe pacotes APENAS do servidor especificado"""
    while True:
        try:
            packet, addr = sock.recvfrom(BUFFER_SIZE + 1)
            if (addr[0] != server_addr[0]) or (addr[1] != server_addr[1]):
                continue
            seq_num = packet[0]
            data = packet[1:]
            if seq_num == expected_seq:
                sock.sendto(f"ACK{seq_num}".encode(), addr)
                return data, addr, 1 - expected_seq
            else:
                sock.sendto(f"ACK{1 - expected_seq}".encode(), addr)
        except socket.timeout:
            continue

def receive_messages(sock, server_addr):
    seq_num = 0
    while not disconnected.is_set():
        try:
            data, _, seq_num = rdt_recv(sock, seq_num, server_addr)
            decoded = data.decode('utf-8')
            if decoded == "disconnected":
                disconnected.set()
                break
            print(f"\n{decoded}\n> ", end='')
        except:
            break

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Não escolhe porta: deixa o sistema escolher automaticamente (como antes)
    # sock.bind(('', 0))  # Omitido: comportamento default já faz isso

    server_ip = socket.gethostbyname(SERVER_HOST)
    server_addr = (server_ip, SERVER_PORT)

    seq_num = 0

    # Login
    username = input("login ")
    login_msg = f"login {username}"
    rdt_send(sock, login_msg.encode('utf-8'), server_addr, seq_num)
    seq_num = 1 - seq_num

    data, _, seq_num = rdt_recv(sock, 0, server_addr)
    decoded = data.decode('utf-8')
    print(decoded)

    if decoded.lower().startswith("erro"):
        sock.close()
        return

    # Thread para receber mensagens
    receiver = threading.Thread(target=receive_messages, args=(sock, server_addr))
    receiver.daemon = True
    receiver.start()

    try:
        while not disconnected.is_set():
            msg = input("> ")
            if disconnected.is_set():
                break
            if msg.lower() == 'logout':
                rdt_send(sock, msg.encode('utf-8'), server_addr, seq_num)
                break
            rdt_send(sock, msg.encode('utf-8'), server_addr, seq_num)
            seq_num = 1 - seq_num
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print("Desconectado.")

if __name__ == "__main__":
    main()

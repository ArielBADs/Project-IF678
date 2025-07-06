import socket
import random
import time

# Configurações
SERVER_HOST = 'localhost'
SERVER_PORT = 1044
BUFFER_SIZE = 1024
TIMEOUT = 1.0  # Tempo limite para receber ACK antes de retransmitir
TAXA_PERDA = 0.1  # Probabilidade de perda simulada de pacotes (20%)

def rdt_send(sock, data, addr, seq_num):
    """Envia um pacote e espera pelo ACK correto antes de continuar"""
    while True:
        if random.random() < TAXA_PERDA:
            print(f"[Cliente] [RDT] Simulando perda do pacote seq={seq_num}, não enviado.")
        else:
            packet = bytes([seq_num]) + data
            sock.sendto(packet, addr)
            print(f"[Cliente] [RDT] Enviado pacote seq={seq_num}, {len(data)} bytes.")

        sock.settimeout(TIMEOUT)
        try:
            ack, _ = sock.recvfrom(10)  # Espera um pequeno ACK
            ack_msg = ack.decode(errors='ignore')
            if ack_msg.strip() == f"ACK{seq_num}":  # Verifica se é o ACK correto
                print(f"[Cliente] [RDT] ACK{seq_num} recebido. Enviando próximo pacote.")
                return  # Sai do loop e segue para o próximo pacote
        except socket.timeout:
            print(f"[Cliente] [RDT] Timeout esperando ACK{seq_num}, retransmitindo...")

def rdt_recv(sock, expected_seq):
    """Recebe pacotes garantindo confiabilidade e envia ACKs corretos"""
    while True:
        try:
            packet, addr = sock.recvfrom(BUFFER_SIZE + 1)  # 1 byte de seq + dados
            seq_num = packet[0]
            data = packet[1:]

            if random.random() < TAXA_PERDA:
                print(f"[Cliente] [RDT] Simulando perda do pacote seq={seq_num}, descartado.")
                continue  # Ignorar pacote perdido

            print(f"[Cliente] [RDT] Pacote recebido seq={seq_num}, {len(data)} bytes.")

            # Verifica se o pacote é o esperado
            if seq_num == expected_seq:
                sock.sendto(f"ACK{seq_num}".encode('utf-8'), addr)
                print(f"[Cliente] [RDT] ACK{seq_num} enviado.")
                return data, addr, 1 - expected_seq  # Alterna sequência

            # Se o pacote for duplicado, reenvia o último ACK
            print(f"[Cliente] [RDT] Pacote seq={seq_num} duplicado. Reenviando último ACK.")
            sock.sendto(f"ACK{1 - expected_seq}".encode('utf-8'), addr)
        except socket.timeout:
            continue  # Aguarda novamente

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_addr = (SERVER_HOST, SERVER_PORT)

    filename = input("Nome do arquivo: ")

    # Enviar nome do arquivo de forma confiável
    print(f"[Cliente] Enviando nome do arquivo: {filename}")
    rdt_send(sock, filename.encode('utf-8'), server_addr, 0)

    # Enviar arquivo fragmentado
    seq_num = 1
    with open(filename, 'rb') as f:
        while True:
            data = f.read(BUFFER_SIZE)
            if not data:
                break
            rdt_send(sock, data, server_addr, seq_num)
            seq_num = 1 - seq_num  # Alterna sequência corretamente

    # Enviar EOF
    rdt_send(sock, b'EOF', server_addr, seq_num)

    # Receber novo nome do arquivo
    new_filename_data, _, seq_num = rdt_recv(sock, 0)
    new_filename = new_filename_data.decode('utf-8')
    print(f"[Cliente] Novo nome recebido: {new_filename}")

    # **Garantir que os pacotes de volta sejam recebidos corretamente**
    with open(new_filename, 'wb') as f:
        seq_num = 0  # Reiniciar sequência para recepção
        while True:
            data, _, seq_num = rdt_recv(sock, seq_num)
            if data == b'EOF':
                break
            f.write(data)

    print(f"[Cliente] Arquivo recebido e salvo como {new_filename}")
    sock.close()

if __name__ == "__main__":
    main()

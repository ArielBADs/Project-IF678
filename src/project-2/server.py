import socket
import random
import string

# Configurações
HOST = 'localhost'
PORT = 1044
BUFFER_SIZE = 1024
TIMEOUT = 1.0
TAXA_PERDA = 0.1  # Simulação de perda de pacotes

def generate_random_name(length=5):
    """Gera um nome aleatório para o arquivo"""
    return ''.join(random.choices(string.ascii_letters, k=length))

def rdt_send(sock, data, addr, seq_num):
    """Envia um pacote e espera pelo ACK correto"""
    while True:
        if random.random() < TAXA_PERDA:
            print(f"[Servidor] [RDT] Simulando perda do pacote seq={seq_num}, não enviado.")
        else:
            packet = bytes([seq_num]) + data
            sock.sendto(packet, addr)
            print(f"[Servidor] [RDT] Enviado pacote seq={seq_num}, {len(data)} bytes.")

        sock.settimeout(TIMEOUT)
        try:
            ack, _ = sock.recvfrom(10)
            ack_msg = ack.decode(errors='ignore').strip()
            if ack_msg == f"ACK{seq_num}":
                print(f"[Servidor] [RDT] ACK{seq_num} recebido. Prosseguindo...")
                return
        except socket.timeout:
            print(f"[Servidor] [RDT] Timeout esperando ACK{seq_num}, retransmitindo...")

def rdt_recv(sock, expected_seq):
    """Recebe pacotes garantindo confiabilidade e envia ACKs corretos"""
    while True:
        try:
            packet, addr = sock.recvfrom(BUFFER_SIZE + 1)  # 1 byte de seq + dados
            seq_num = packet[0]
            data = packet[1:]

            if random.random() < TAXA_PERDA:
                print(f"[Servidor] [RDT] Simulando perda do pacote seq={seq_num}, descartado.")
                continue  # Ignorar pacote perdido

            print(f"[Servidor] [RDT] Pacote recebido seq={seq_num}, {len(data)} bytes.")

            # Verifica se o pacote é o esperado
            if seq_num == expected_seq:
                sock.sendto(f"ACK{seq_num}".encode('utf-8'), addr)
                print(f"[Servidor] [RDT] ACK{seq_num} enviado.")
                return data, addr, 1 - expected_seq  # Alterna sequência

            # Se o pacote for duplicado, reenvia o último ACK
            print(f"[Servidor] [RDT] Pacote seq={seq_num} duplicado. Reenviando último ACK.")
            sock.sendto(f"ACK{1 - expected_seq}".encode('utf-8'), addr)
        except socket.timeout:
            continue  # Aguarda novamente

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"[Servidor] Escutando em {HOST}:{PORT}")

    while True:
        # Receber nome do arquivo
        filename_data, client_addr, seq_num = rdt_recv(sock, 0)
        filename = filename_data.decode('utf-8')
        print(f"[Servidor] Recebendo arquivo: {filename}")

        # Receber arquivo na memória
        file_data = []
        while True:
            data, _, seq_num = rdt_recv(sock, seq_num)
            if data == b'EOF':
                break
            file_data.append(data)

        print(f"[Servidor] Arquivo {filename} recebido e armazenado na memória.")

        # Gerar nome aleatório para o arquivo
        new_filename = generate_random_name() + "_" + filename
        rdt_send(sock, new_filename.encode('utf-8'), client_addr, 0)

        # **Garantir que o arquivo de volta seja enviado corretamente**
        seq_num = 0  # Reiniciar sequência para o envio

        for chunk in file_data:
            rdt_send(sock, chunk, client_addr, seq_num)
            seq_num = 1 - seq_num  # Alternar sequência

        # Enviar EOF para sinalizar fim da transmissão
        rdt_send(sock, b'EOF', client_addr, seq_num)
        print(f"[Servidor] Arquivo {new_filename} enviado de volta ao cliente.")

if __name__ == "__main__":
    main()

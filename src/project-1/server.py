import socket
import random

def generate_random_name(length=5): # Gera uma string aleatória para inserir no nome do arquivo
    letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return ''.join(random.choices(letters, k=length))

def main(host='localhost', port=1044):
    addr = (host, port)
    buffer_size = 1024

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(addr)

    print(f"Servidor UDP escutando em {addr}")

    while True:
        data, client_addr = udp.recvfrom(buffer_size)
        filename = data.decode('utf-8') # Recebe o arquivo enviado do client
        print(f"Recebendo arquivo: {filename}")

        random_name = generate_random_name()
        new_filename = f"{random_name}_{filename}" # Cria o novo nome do arquivo para ser enviado ao client
        udp.sendto(new_filename.encode('utf-8'), client_addr)

        file_data = [] # Armazenar os fragmentos recebidos
        while True:
            data, client_addr = udp.recvfrom(buffer_size) # Recebe cada fragmento de até 1024 bytes
            if data == b'EOF':
                break
            file_data.append(data) # Adiciona cada fragmento na lista

        print(f"Arquivo {filename} recebido e nome alterado para {new_filename}")

        for chunk in file_data: # Envia cada fragmento de volta ao client
            udp.sendto(chunk, client_addr)
        udp.sendto(b'', client_addr)

        print(f"Arquivo {new_filename} enviado de volta ao client")

if __name__ == "__main__":
    main()

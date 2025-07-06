import socket

def main(host='localhost', port=1044):
    addr = (host, port)
    buffer_size = 1024

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    filename = input("Nome do arquivo: ")
    udp.sendto(filename.encode('utf-8'), addr) # Envia o arquivo descrito no input

    print(f"Enviando arquivo: {filename}")

    with open(filename, 'rb') as f:
        while True:
            data = f.read(buffer_size) # Lê o arquivo em fragmentos de tamanho 1024 bytes
            if not data: # Encerra o loop caso não tenha mais dados para ler
                break
            udp.sendto(data, addr) # Envia cada fragmento para o servidor
        udp.sendto(b'EOF', addr)

    print(f"Arquivo {filename} enviado!")

    new_filename_data, server_addr = udp.recvfrom(buffer_size) # Recebe o arquivo com o nome alterado
    new_filename = new_filename_data.decode('utf-8')  # Decodifica o arquivo
    print(f"Servidor alterou o nome do arquivo para: {new_filename}")

    with open(new_filename, 'wb') as f:
        while True:
            data, server_addr = udp.recvfrom(buffer_size) # Recebe cada fragmento enviado de volta do servidor.
            if data == b'':
                break
            f.write(data) # Escreve o fragmento no arquivo

    print(f"Arquivo recebido e salvo como {new_filename}")

    udp.close()

if __name__ == "__main__":
    main()

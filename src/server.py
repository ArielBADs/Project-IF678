import socket
import random
import string
import threading
import time
from collections import defaultdict

# Configurações
HOST = 'localhost'
PORT = 1044
BUFFER_SIZE = 1024
TIMEOUT = 0.4

clients = set()  # Armazena endereços dos clientes
client_names = {}  # Mapeia endereços para nomes
username_to_addr = {}  # Mapeia nomes para endereços
client_lock = threading.Lock()
client_locks = defaultdict(threading.Lock)  # Lock por cliente

friends = defaultdict(set)  # Usuário segue outros
groups = {}  # Chave: (admin, group_name), Valor: {key, members, created_at}
client_state = defaultdict(lambda: {
    "expected_seq": 0,
    "send_seq": 0
})

def rdt_send(sock, data, addr):
    retries = 10
    seq_num = client_state[addr]['send_seq']
    while True:
        packet = bytes([seq_num]) + data
        sock.sendto(packet, addr)
        print(f"[Servidor] [RDT] Enviado seq={seq_num} para {addr}")

        sock.settimeout(TIMEOUT)
        try:
            ack, _ = sock.recvfrom(10)
            if ack.decode().strip() == f"ACK{seq_num}":
                print(f"[Servidor] [RDT] ACK{seq_num} recebido de {addr}")
                client_state[addr]['send_seq'] = 1 - seq_num
                return
        except socket.timeout:
            print(f"[Servidor] [RDT] Timeout esperando ACK{seq_num} de {addr}")

def rdt_recv(sock, client_addr):
    while True:
        try:
            packet, addr = sock.recvfrom(BUFFER_SIZE + 1)
            if addr != client_addr:
                continue
            seq_num = packet[0]
            data = packet[1:]

            expected_seq = client_state[client_addr]['expected_seq']
            print(f"[Servidor] [RDT] Recebido seq={seq_num} de {addr}")

            if seq_num == expected_seq:
                sock.sendto(f"ACK{seq_num}".encode(), addr)
                client_state[client_addr]['expected_seq'] = 1 - expected_seq
                return data, addr
            else:
                sock.sendto(f"ACK{1 - expected_seq}".encode(), addr)

        except socket.timeout:
            continue


def broadcast_notification(sock, message, exclude_addr=None):
    """Envia notificação para todos os clientes, exceto exclude_addr"""
    with client_lock:
        for addr in clients:
            if addr != exclude_addr:
                with client_locks[addr]:
                    rdt_send(sock, message.encode('utf-8'), addr)

def handle_client(sock, client_addr):
    print(f"[Servidor] Novo cliente conectado: {client_addr}")
    current_user = None

    try:
        data, _ = rdt_recv(sock,  client_addr)
        message = data.decode('utf-8').strip()
        if not message.startswith("login "):
            raise ValueError("Comando login não recebido.")
        username = message.split()[1]
        
        with client_lock:
            if username in username_to_addr:
                response = "Erro: Nome de usuário já está em uso."
                with client_locks[client_addr]:
                    rdt_send(sock, response.encode('utf-8'), client_addr)
                return
            clients.add(client_addr)
            client_names[client_addr] = username
            username_to_addr[username] = client_addr
            current_user = username
        
        # Confirmar login
        response = "Você está online!"
        with client_locks[client_addr]:
            rdt_send(sock, response.encode('utf-8'), client_addr)

        print(f"[Servidor] Cliente {client_addr} registrado como '{username}'")

        while True:
            data, _ = rdt_recv(sock, client_addr)
            message = data.decode('utf-8').strip()
            if not message:
                continue

            if message.lower() == 'logout':
                with client_lock:
                    if client_addr in clients:
                        clients.remove(client_addr)
                    if client_addr in client_names:
                        del username_to_addr[client_names[client_addr]]
                        del client_names[client_addr]
                    if current_user in friends:
                        del friends[current_user]
                    # Remover de grupos
                    for group_id in list(groups.keys()):
                        if current_user in groups[group_id]['members']:
                            groups[group_id]['members'].remove(current_user)
                            if not groups[group_id]['members']:
                                del groups[group_id]
                print(f"[Servidor] Cliente {client_addr} desconectado.")
                break

            parts = message.split()
            command = parts[0].lower()

            response = ""
            if command == 'list:cinners':
                with client_lock:
                    cinners = [f"{client_names[addr]} {addr[0]}:{addr[1]}" for addr in clients]
                    response = "\n".join(cinners) if cinners else "Nenhum usuário conectado."

            elif command == 'follow':
                if len(parts) < 2:
                    response = "Erro: Comando follow requer <nome_do_usuario>."
                else:
                    target = parts[1]
                    if target == current_user:
                        response = "Erro: Não pode seguir a si mesmo."
                    elif target not in username_to_addr:
                        response = f"Erro: Usuário {target} não encontrado."
                    elif target in friends[current_user]:
                        response = f"Você já está seguindo {target}."
                    else:
                        friends[current_user].add(target)
                        response = f"{target} foi adicionado à sua lista de amigos."
                        target_addr = username_to_addr.get(target)
                        if target_addr:
                            notification = f"Você foi seguido por {current_user} {client_addr[0]}:{client_addr[1]}"
                            with client_locks[target_addr]:
                                rdt_send(sock, notification.encode(), target_addr)

            elif command == 'create_group':
                if len(parts) < 2:
                    response = "Erro: Nome do grupo necessário."
                else:
                    group_name = parts[1]
                    group_id = (current_user, group_name)
                    if group_id in groups:
                        response = f"Erro: Você já possui um grupo '{group_name}'."
                    else:
                        key = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                        groups[group_id] = {
                            'key': key,
                            'members': {current_user},
                            'admin': current_user,
                            'created_at': time.time()
                        }
                        response = f"Grupo '{group_name}' criado com sucesso. Chave: {key}"

            elif command == 'list:groups':
                user_groups = []
                for (admin, name), info in groups.items():
                    if current_user in info['members']:
                        user_groups.append(f"Nome: {name}, Admin: {admin}, Criado em: {time.ctime(info['created_at'])}")
                response = "\n".join(user_groups) if user_groups else "Você não está em nenhum grupo."

            elif command == 'list:friends':
                # Amigos mútuos (quando ambos se seguem)
                mutual_friends = []
                for followed in friends[current_user]:
                    # Verifica se o followed também está seguindo o current_user
                    if current_user in friends.get(followed, set()):
                        mutual_friends.append(followed)
                response = "\n".join(mutual_friends) if mutual_friends else "Você não tem amigos mútuos."

            elif command == 'list:mygroups':
                # Grupos criados pelo usuário
                my_groups = []
                for (admin, group_name), info in groups.items():
                    if admin == current_user:
                        my_groups.append(f"Nome: {group_name}, Chave: {info['key']}")
                response = "\n".join(my_groups) if my_groups else "Você não criou nenhum grupo."

            
            elif command == 'unfollow':
                if len(parts) < 2:
                    response = "Erro: Comando unfollow requer <nome_do_usuario>."
                else:
                    target = parts[1]
                    if target not in friends[current_user]:
                        response = f"Erro: Você não está seguindo {target}."
                    else:
                        friends[current_user].remove(target)
                        response = f"Você deixou de seguir {target}."
                        # Notificar o usuário que foi deixado de seguir
                        target_addr = username_to_addr.get(target)
                        if target_addr:
                            notification = f"[{current_user}/{client_addr[0]}:{client_addr[1]}] {current_user} deixou de seguir você"
                            with client_locks[target_addr]:
                                rdt_send(sock, notification.encode(), target_addr)

            elif command == 'delete_group':
                if len(parts) < 2:
                    response = "Erro: Comando delete_group requer <nome_do_grupo>."
                else:
                    group_name = parts[1]
                    group_id = (current_user, group_name)
                    if group_id not in groups:
                        response = f"Erro: Grupo '{group_name}' não encontrado ou você não é o administrador."
                    else:
                        # Remove o grupo e notifica os membros
                        members = groups[group_id]['members'].copy()
                        del groups[group_id]
                        response = f"Grupo '{group_name}' deletado com sucesso."
                        # Notifica todos os membros
                        notification = f"[{current_user}/{client_addr[0]}:{client_addr[1]}] O grupo {group_name} foi deletado pelo administrador"
                        for member in members:
                            if member != current_user:  # Não envia para o próprio admin
                                member_addr = username_to_addr.get(member)
                                if member_addr:
                                    with client_locks[member_addr]:
                                        rdt_send(sock, notification.encode(), member_addr)

            elif command == 'join':
                if len(parts) < 3:
                    response = "Erro: Comando join requer <nome_do_grupo> <chave_grupo>."
                else:
                    group_name = parts[1]
                    key = parts[2]
                    # Procura o grupo em todos os administradores
                    found = False
                    for (admin, name), info in groups.items():
                        if name == group_name and info['key'] == key:
                            found = True
                            if current_user in info['members']:
                                response = "Você já está neste grupo."
                            else:
                                info['members'].add(current_user)
                                response = f"Você entrou no grupo '{group_name}'."
                                # Notifica todos os membros
                                notification = f"[{current_user}/{client_addr[0]}:{client_addr[1]}] {current_user} acabou de entrar no grupo"
                                for member in info['members']:
                                    if member != current_user:  # Não envia para o novo membro
                                        member_addr = username_to_addr.get(member)
                                        if member_addr:
                                            with client_locks[member_addr]:
                                                rdt_send(sock, notification.encode(), member_addr)
                            break
                    if not found:
                        response = "Erro: Grupo não encontrado ou chave inválida."
            elif command == 'leave':
                if len(parts) < 2:
                    response = "Erro: Comando leave requer <nome_do_grupo>."
                else:
                    group_name = parts[1]
                    left = False
                    # Procura o grupo em todos os administradores
                    for (admin, name), info in groups.items():
                        if name == group_name and current_user in info['members']:
                            info['members'].remove(current_user)
                            left = True
                            response = f"Você saiu do grupo '{group_name}'."
                            # Notifica todos os membros
                            notification = f"[{current_user}/{client_addr[0]}:{client_addr[1]}] {current_user} saiu do grupo"
                            for member in info['members']:
                                member_addr = username_to_addr.get(member)
                                if member_addr:
                                    with client_locks[member_addr]:
                                        rdt_send(sock, notification.encode(), member_addr)
                            break
                    if not left:
                        response = f"Erro: Você não está no grupo '{group_name}'."

            elif command == 'ban':
                if len(parts) < 2:
                    response = "Erro: Comando ban requer <nome_do_usuario>."
                else:
                    target = parts[1]
                    banned = False
                    # Procura grupos onde o usuário é admin
                    for (admin, group_name), info in groups.items():
                        if admin == current_user and target in info['members']:
                            # Remove o usuário do grupo
                            info['members'].remove(target)
                            banned = True
                            # Notifica membros (exceto o banido)
                            notification_members = f"{target} foi banido do grupo"
                            for member in info['members']:
                                member_addr = username_to_addr.get(member)
                                if member_addr:
                                    with client_locks[member_addr]:
                                        rdt_send(sock, notification_members.encode(), member_addr)
                            # Notifica o banido
                            notification_banned = f"[{current_user}/{client_addr[0]}:{client_addr[1]}] O administrador do grupo {group_name} baniu você."
                            target_addr = username_to_addr.get(target)
                            if target_addr:
                                with client_locks[target_addr]:
                                    rdt_send(sock, notification_banned.encode(), target_addr)
                            response = f"{target} foi banido do grupo."
                            break
                    if not banned:
                        response = "Erro: Você não é admin de um grupo onde este usuário está."

            elif command == 'chat_group':
                if len(parts) < 4:
                    response = "Erro: Formato: chat_group <nome_grupo> <chave> <mensagem>"
                else:
                    group_name = parts[1]
                    key = parts[2]
                    message = ' '.join(parts[3:])
                    valid = False
                    # Valida grupo e chave
                    for (admin, name), info in groups.items():
                        if name == group_name and info['key'] == key and current_user in info['members']:
                            valid = True
                            # Envia mensagem para todos os membros (exceto remetente)
                            formatted_msg = f"[{current_user}/{client_addr[0]}:{client_addr[1]}] {message}"
                            for member in info['members']:
                                if member != current_user:
                                    member_addr = username_to_addr.get(member)
                                    if member_addr:
                                        with client_locks[member_addr]:
                                            rdt_send(sock, formatted_msg.encode(), member_addr)
                            response = "Mensagem enviada ao grupo."
                            break
                    if not valid:
                        response = "Erro: Grupo não encontrado, chave inválida ou você não é membro."
            
            elif command == 'chat_friend':
                if len(parts) < 3:
                    response = "Erro: Formato: chat_friend <nome_amigo> <mensagem>"
                else:
                    friend_name = parts[1]
                    message = ' '.join(parts[2:])
                    
                    # Verifica se é amigo mútuo
                    is_mutual = (friend_name in friends[current_user] and 
                                current_user in friends.get(friend_name, set()))
                    
                    if not is_mutual:
                        response = "Erro: Você só pode enviar mensagens para amigos mútuos."
                    elif friend_name not in username_to_addr:
                        response = f"Erro: {friend_name} não está online."
                    else:
                        friend_addr = username_to_addr[friend_name]
                        formatted_msg = f"[{current_user}/{client_addr[0]}:{client_addr[1]}] {message}"
                        
                        with client_locks[friend_addr]:
                            rdt_send(sock, formatted_msg.encode(), friend_addr)
                        
                        response = f"Mensagem enviada para {friend_name}."

            else:
                response = "Erro: Comando não reconhecido."

            with client_locks[client_addr]:
                rdt_send(sock, response.encode('utf-8'), client_addr)

    except Exception as e:
        print(f"[Servidor] Erro com cliente {client_addr}: {e}")
    finally:
        with client_lock:
            if client_addr in clients:
                clients.remove(client_addr)
            if client_addr in client_names:
                del username_to_addr[client_names[client_addr]]
                del client_names[client_addr]
            if current_user in friends:
                del friends[current_user]
            # Remover de grupos
            for group_id in list(groups.keys()):
                if current_user in groups[group_id]['members']:
                    groups[group_id]['members'].remove(current_user)
                    if not groups[group_id]['members']:
                        del groups[group_id]
        try:
            response = "disconnected"
            rdt_send(sock, response.encode('utf-8'), client_addr)
        except Exception as e:
            print(f"[Servidor] Cliente já esta desconectado no client.")
        

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    sock.settimeout(TIMEOUT)
    print(f"[Servidor] Chat servidor escutando em {HOST}:{PORT}")

    while True:
        try:
            data, client_addr = sock.recvfrom(BUFFER_SIZE)
            with client_lock:
                if client_addr not in clients:
                    thread = threading.Thread(target=handle_client, args=(sock, client_addr))
                    thread.daemon = True
                    thread.start()
        except socket.timeout:
            continue

if __name__ == "__main__":
    main()
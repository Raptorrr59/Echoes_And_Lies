# === SERVER AND CLIENT CODE UPDATED FOR AI, VOTE LOGGING, AND WHISPERER INFO ===

import socket
import threading
import random
import queue
import time
import sys
import pygame

HOST = 'localhost'
PORT = 12345

echoes_bank = [
    ("The stars speak only to those who listen.", True),
    ("The world was flat before the Great Turn.", False),
    ("Magic once flowed through rivers like water.", True),
    ("Books can whisper only to Whisperers.", False),
    ("Truth is hidden in the third shelf of the East Wing.", True),
    ("Only lies can open the final door.", False),
]

clients = []
client_names = {}
roles = {}
votes_queue = {}
message_queues = {}
ais = set()
lock = threading.Lock()

current_round = 0
max_rounds = 3
accepted_lies = 0

running = True

def send_line(client, message):
    try:
        client.sendall((message + "\n").encode())
    except:
        pass

def broadcast(message):
    for client in clients:
        send_line(client, message)

def handle_client(conn, addr):
    name = conn.recv(1024).decode().strip()
    print(f"{name} joined from {addr}")
    with lock:
        clients.append(conn)
        client_names[conn] = name
        message_queues[conn] = queue.Queue()
        votes_queue[conn] = queue.Queue()
        if name.lower().startswith("ai"):
            ais.add(conn)

    try:
        while running:
            data = conn.recv(1024)
            if not data:
                break
            msg = data.decode().strip()
            votes_queue[conn].put(msg)
    except:
        pass
    finally:
        with lock:
            if conn in clients:
                clients.remove(conn)
            conn.close()

def ai_vote(echoes, role):
    true_indices = [i for i, e in enumerate(echoes) if e[1]]
    false_indices = [i for i, e in enumerate(echoes) if not e[1]]
    if role == "Explorer":
        if random.random() < 0.5:
            return random.choice(true_indices) + 1
        else:
            return random.choice(false_indices) + 1
    else:
        if random.random() < 0.7:
            return random.choice(false_indices) + 1
        else:
            return random.choice(true_indices) + 1

def game_loop():
    global current_round, accepted_lies, running
    print("Press Enter to start the game...")
    input()

    broadcast("Welcome to Echoes & Lies!\n")
    broadcast("--- ROLE EXPLANATIONS ---")
    broadcast("Whisperer: Knows which echoes are false and tries to mislead the others.")
    broadcast("Explorer: Tries to identify and vote for the true echo among the three.")
    broadcast("Two true echoes and one false are shown each round.")
    broadcast("Choose carefully! Too many lies and the library is lost...\n")

    while current_round < max_rounds:
        with lock:
            whisperer = random.choice(clients)
            for c in clients:
                roles[c] = "Whisperer" if c == whisperer else "Explorer"

            echoes = random.sample(echoes_bank, 3)
            if sum(1 for e in echoes if e[1]) != 2:
                continue

            for c in clients:
                send_line(c, f"ROLE:{roles[c]}")
                for idx, (text, is_true) in enumerate(echoes):
                    send_line(c, f"ECHO {idx+1}: {text}")
                if roles[c] == "Whisperer":
                    for idx, (_, is_true) in enumerate(echoes):
                        if not is_true:
                            send_line(c, f"NOTE: Echo {idx+1} is the lie.")

        votes = {}
        for c in clients:
            try:
                send_line(c, "Choose the echo you believe is TRUE (1/2/3):")
                if c in ais:
                    vote = ai_vote(echoes, roles[c])
                else:
                    vote = votes_queue[c].get(timeout=30)
                votes[c] = int(vote)
            except:
                votes[c] = 1

        vote_counts = {}
        for v in votes.values():
            vote_counts[v] = vote_counts.get(v, 0) + 1

        # Find the echo number (1/2/3) with the most votes
        chosen = max(vote_counts.items(), key=lambda item: item[1])[0]
        selected_echo = echoes[chosen - 1]

        broadcast("--- Round Results ---")
        round_summary = []
        for c in clients:
            name = client_names.get(c, "Unknown")
            vote = votes.get(c, "?")
            line = f"{name} voted for Echo {vote}."
            broadcast(line)
            round_summary.append(line)

        if not selected_echo[1]:
            accepted_lies += 1
            outcome_msg = "The chosen echo was a LIE! Library corruption increases."
        else:
            outcome_msg = "The chosen echo was TRUE. Wisdom preserved."

        broadcast(outcome_msg)
        round_summary.append(outcome_msg)

        # Send summary to each client (for GUI rendering)
        for c in clients:
            for line in round_summary:
                send_line(c, f"SUMMARY: {line}")

        current_round += 1
        time.sleep(2)

    if accepted_lies >= 2:
        broadcast("Whisperer wins! Lies have corrupted the library.")
    else:
        broadcast("Explorers win! The truth has been preserved.")

    running = False

def start_server():
    print(f"Server starting on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        threading.Thread(target=game_loop, daemon=True).start()
        try:
            while running:
                conn, addr = s.accept()
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\nServer shutting down...")
            s.close()
            sys.exit(0)

# === CLIENT CODE (with physics/visual echo orbs using pygame) ===

def start_client():
    import pygame
    import threading

    name = input("Enter your name: ")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    s.sendall(name.encode())

    WIDTH, HEIGHT = 800, 600
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Echoes & Lies - Echo Orbs")
    font = pygame.font.SysFont(None, 24)

    clock = pygame.time.Clock()

    orbs = []
    messages = []
    vote_ready = False

    class Orb:
        def __init__(self, text, idx):
            self.text = text
            self.x = 200 + idx * 200
            self.y = HEIGHT // 2 + 50
            self.vx = 0
            self.vy = 0
            self.radius = 75
            self.color = (100 + idx * 50, 100, 255 - idx * 80)
            self.idx = idx + 1

        def update(self):
            self.vy += 0.2
            self.y += self.vy
            if self.y > HEIGHT - self.radius:
                self.y = HEIGHT - self.radius
                self.vy *= -0.5

        def draw(self):
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
            idx_text = font.render(f"{self.idx}", True, (255, 255, 255))
            text_lines = wrap_text(self.text, font, 160)
            for i, line in enumerate(text_lines):
                line_surf = font.render(line, True, (255, 255, 255))
                screen.blit(line_surf, (self.x - line_surf.get_width() // 2, self.y + 10 + i * 20))
            screen.blit(idx_text, (self.x - idx_text.get_width() // 2, self.y - 10))

# helper function

    def wrap_text(text, font, max_width):
        words = text.split(' ')
        lines = []
        current = ''
        for word in words:
            test_line = current + word + ' '
            if font.size(test_line)[0] <= max_width:
                current = test_line
            else:
                lines.append(current.strip())
                current = word + ' '
        lines.append(current.strip())
        return lines

    def handle_server():
        nonlocal vote_ready, orbs, messages
        buffer = ""
        current_echoes = []
        while True:
            try:
                chunk = s.recv(1024).decode()
                if not chunk:
                    break
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("ROLE:"):
                        role = line.split(":", 1)[1].strip()
                        messages.append(f"--- Your role is {role} ---")
                    elif line.startswith("NOTE:"):
                        messages.append(f"{line}")
                    elif line.startswith("SUMMARY:"):
                        messages.append(line[8:].strip())
                    elif line.startswith("ECHO"):
                        current_echoes.append(line.split(": ", 1)[1])
                        if len(current_echoes) == 3:
                            orbs = [Orb(text, idx) for idx, text in enumerate(current_echoes)]
                            current_echoes.clear()
                    elif "Choose the echo" in line:
                        vote_ready = True
                        messages.append("Vote for the echo you believe is TRUE.")
                    elif "wins" in line or "Wisdom" in line or "corruption" in line:
                        messages.append(line)
            except:
                break

    threading.Thread(target=handle_server, daemon=True).start()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and vote_ready:
                mx, my = pygame.mouse.get_pos()
                for orb in orbs:
                    dx = mx - orb.x
                    dy = my - orb.y
                    if dx * dx + dy * dy <= orb.radius * orb.radius:
                        s.sendall(str(orb.idx).encode())
                        vote_ready = False
                        break

        screen.fill((20, 20, 40))

        for orb in orbs:
            orb.update()
            orb.draw()

        y_offset = 10
        for msg in messages[-5:]:
            surf = font.render(msg, True, (255, 255, 255))
            screen.blit(surf, (10, y_offset))
            y_offset += 24

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    s.close()

if __name__ == '__main__':
    mode = input("Start as (server/client): ").strip().lower()
    if mode == 'server':
        start_server()
    elif mode == 'client':
        start_client()
    else:
        print("Invalid mode. Choose 'server' or 'client'.")

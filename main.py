"""Snake Game com dificuldades, pausa, pontuações locais e menus."""
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import random

import pygame
from storage import MODES, data_file, load_profile, record_round, save_profile

GRID = 30
CELL = 20
BOARD_SIZE = GRID * CELL
HEADER = 72
FOOTER = 42
SIZE = (BOARD_SIZE, BOARD_SIZE + HEADER + FOOTER)
DIFFICULTIES = {"easy": ("Fácil", 6, 12), "normal": ("Normal", 9, 16), "hard": ("Difícil", 12, 20)}
UP, RIGHT, DOWN, LEFT = (0, -1), (1, 0), (0, 1), (-1, 0)


def speed_for(mode, score):
    _, initial, maximum = DIFFICULTIES[mode]
    return min(initial + max(0, score) // 5, maximum)


def make_icon():
    icon = pygame.Surface((32, 32))
    icon.fill((12, 12, 12))
    pygame.draw.lines(icon, (240, 240, 240), False, [(6, 25), (6, 8), (20, 8), (20, 22)], 6)
    pygame.draw.rect(icon, (235, 62, 62), (24, 24, 6, 6))
    return icon


class SnakeGame:
    """Coordenadas em células; o desenho converte as posições em pixels."""

    def __init__(self, difficulty="normal"):
        self.difficulty = difficulty
        self.reset()

    def reset(self):
        center = GRID // 2
        self.snake = [(center, center), (center + 1, center), (center + 2, center)]
        self.direction = self.next_direction = LEFT
        self.turn_pending = False
        self.score = 0
        self.state = "ready"
        self.apple = self.spawn_apple()

    def spawn_apple(self):
        occupied = set(self.snake)
        free = [(x, y) for y in range(GRID) for x in range(GRID) if (x, y) not in occupied]
        return random.choice(free) if free else None

    def turn(self, direction):
        if self.state != "playing" or self.turn_pending or direction not in (UP, RIGHT, DOWN, LEFT):
            return
        opposite = (-self.direction[0], -self.direction[1])
        if direction not in (self.direction, opposite):
            self.next_direction = direction
            self.turn_pending = True

    def step(self):
        if self.state != "playing":
            return
        self.direction = self.next_direction
        self.turn_pending = False
        head = (self.snake[0][0] + self.direction[0], self.snake[0][1] + self.direction[1])
        grows = head == self.apple
        # A cauda libera sua célula neste passo, exceto quando a cobra cresce.
        body = self.snake if grows else self.snake[:-1]
        if not (0 <= head[0] < GRID and 0 <= head[1] < GRID) or head in body:
            self.state = "over"
            return
        self.snake.insert(0, head)
        if grows:
            self.score += 1
            self.apple = self.spawn_apple()
            if self.apple is None:
                self.state = "won"
        else:
            self.snake.pop()


class App:
    def __init__(self, profile_path=None):
        pygame.init()
        self.profile_path = Path(profile_path) if profile_path else data_file()
        self.profile = load_profile(self.profile_path)
        self.notice = ""
        self.pending_save = False
        self.fullscreen = False
        desktop = pygame.display.get_desktop_sizes()[0]
        scale = min(1, max(1, desktop[0] - 80) / SIZE[0], max(1, desktop[1] - 100) / SIZE[1])
        self.window_size = tuple(max(1, int(value * scale)) for value in SIZE)
        self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        if self.profile["settings"]["fullscreen"]:
            self.set_fullscreen(True)
        pygame.display.set_caption("Snake Game")
        pygame.display.set_icon(make_icon())
        self.canvas = pygame.Surface(SIZE)
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.Font(None, 56)
        self.number_font = pygame.font.Font(None, 96)
        self.brand_font = pygame.font.Font(None, 36)
        self.font = pygame.font.Font(None, 26)
        self.small_font = pygame.font.Font(None, 22)
        self.game = SnakeGame(self.profile["settings"]["difficulty"])
        self.running = True
        self.elapsed = 0.0
        self.duration = 0.0
        self.countdown = 0.0
        self.round_active = False
        self.new_record = False
        self.menu_index = 0
        self.history_page = 0
        self.view_mode = self.game.difficulty
        self.speed_notice = 0.0

    def save(self):
        self.pending_save = True
        try:
            save_profile(self.profile_path, self.profile)
            self.notice = ""
            self.pending_save = False
        except OSError:
            self.notice = "Dados não salvos. Verifique o acesso à pasta local."

    def set_fullscreen(self, enabled):
        try:
            if enabled:
                self.window_size = self.screen.get_size()
            self.screen = pygame.display.set_mode((0, 0) if enabled else self.window_size,
                                                  pygame.FULLSCREEN if enabled else pygame.RESIZABLE)
            self.fullscreen = enabled
            return True
        except pygame.error:
            self.notice = "Tela cheia indisponível."
            return False

    def start(self):
        self.game.difficulty = self.profile["settings"]["difficulty"]
        self.game.reset()
        self.duration = 0.0
        self.elapsed = 0.0
        self.round_active = False
        self.new_record = False
        self.speed_notice = 0.0
        self.resume()

    def resume(self):
        self.game.state = "countdown"
        self.countdown = 3.0
        self.menu_index = 0

    def finish(self, result):
        if self.round_active:
            self.new_record = record_round(self.profile, self.game.difficulty, self.game.score, self.duration, result)
            self.round_active = False
            self.save()
        self.menu_index = 0

    def buttons(self):
        state = self.game.state
        if state == "ready":
            items = [("Jogar", "play"), ("Pontuações", "ranking"), ("Configurações", "settings"), ("Sair", "exit")]
            return [(pygame.Rect(60, 330 + index * 64, 480, 50), label, action) for index, (label, action) in enumerate(items)]
        if state == "settings":
            mode = DIFFICULTIES[self.profile["settings"]["difficulty"]][0]
            items = [(f"Dificuldade: {mode}", "difficulty"),
                     ("Tela: " + ("cheia" if self.fullscreen else "janela"), "fullscreen"), ("Voltar", "menu")]
            return [(pygame.Rect(60, 300 + index * 70, 480, 54), label, action) for index, (label, action) in enumerate(items)]
        if state in ("over", "won", "paused"):
            items = [("Continuar", "resume") if state == "paused" else ("Jogar novamente", "play"), ("Menu inicial", "menu")]
            start = 332 if state == "paused" else 486
            return [(pygame.Rect(60, start + index * 64, 480, 50), label, action) for index, (label, action) in enumerate(items)]
        if state in ("ranking", "history"):
            items = [(pygame.Rect(48, 175, 245, 42), "Modo: " + DIFFICULTIES[self.view_mode][0], "view_mode"),
                     (pygame.Rect(307, 175, 245, 42), "Ver histórico" if state == "ranking" else "Ver Top 5", "history" if state == "ranking" else "ranking")]
            if state == "history":
                items.extend([(pygame.Rect(48, 546, 245, 42), "Anterior", "previous"),
                              (pygame.Rect(307, 546, 245, 42), "Próxima", "next")])
            return items + [(pygame.Rect(48, 603, 504, 46), "Voltar", "menu")]
        return []

    def activate(self, action):
        if action == "play":
            self.start()
        elif action == "resume":
            self.resume()
        elif action == "exit":
            self.finish("interrupted")
            if self.pending_save:
                self.save()
            self.running = False
        elif action == "menu":
            self.finish("interrupted")
            self.game.state = "ready"
            self.menu_index = 0
        elif action in ("ranking", "history", "settings"):
            if self.game.state == "ready":
                self.view_mode = self.profile["settings"]["difficulty"]
            self.game.state = action
            self.history_page = self.menu_index = 0
        elif action == "difficulty":
            current = self.profile["settings"]["difficulty"]
            self.profile["settings"]["difficulty"] = MODES[(MODES.index(current) + 1) % len(MODES)]
            self.save()
        elif action == "view_mode":
            self.view_mode = MODES[(MODES.index(self.view_mode) + 1) % len(MODES)]
            self.history_page = 0
        elif action == "fullscreen":
            if self.set_fullscreen(not self.fullscreen):
                self.profile["settings"]["fullscreen"] = self.fullscreen
                self.save()
            if self.game.state in ("playing", "countdown"):
                self.game.state = "paused"
                self.menu_index = 0
        elif action in ("previous", "next"):
            rows = self.profile["scores"][self.view_mode]["history"]
            pages = max(1, math.ceil(len(rows) / 5))
            self.history_page = (self.history_page + (1 if action == "next" else -1)) % pages

    def scene_geometry(self):
        width, height = self.screen.get_size()
        scale = min(width / SIZE[0], height / SIZE[1])
        size = (max(1, round(SIZE[0] * scale)), max(1, round(SIZE[1] * scale)))
        return pygame.Rect((width - size[0]) // 2, (height - size[1]) // 2, *size)

    def logical_point(self, point):
        area = self.scene_geometry()
        if not area.collidepoint(point):
            return None
        return ((point[0] - area.x) * SIZE[0] / area.width, (point[1] - area.y) * SIZE[1] / area.height)

    def handle_event(self, event):
        if not self.running:
            return
        if event.type == pygame.QUIT:
            self.activate("exit")
        elif event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED) and self.game.state in ("playing", "countdown"):
            self.game.state = "paused"
            self.menu_index = 0
        elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
            if self.game.state in ("playing", "countdown"):
                self.game.state = "paused"
                self.menu_index = 0
            self.window_size = (max(1, event.w), max(1, event.h))
            self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        elif event.type == pygame.MOUSEMOTION:
            point = self.logical_point(event.pos)
            if point is not None:
                for index, (rect, _, _) in enumerate(self.buttons()):
                    if rect.collidepoint(point):
                        self.menu_index = index
                        break
        elif event.type == pygame.KEYDOWN:
            state = self.game.state
            if event.key == pygame.K_ESCAPE:
                if state == "ready":
                    self.activate("exit")
                elif state in ("playing", "countdown"):
                    self.game.state = "paused"
                    self.menu_index = 0
                elif state == "paused":
                    self.resume()
                else:
                    self.activate("menu")
            elif event.key == pygame.K_F11:
                self.activate("fullscreen")
            elif event.key == pygame.K_p and state in ("playing", "countdown", "paused"):
                if state == "paused":
                    self.resume()
                else:
                    self.game.state = "paused"
                    self.menu_index = 0
            elif state == "playing":
                directions = {pygame.K_UP: UP, pygame.K_RIGHT: RIGHT, pygame.K_DOWN: DOWN, pygame.K_LEFT: LEFT}
                if event.key in directions:
                    self.game.turn(directions[event.key])
            elif state != "countdown":
                buttons = self.buttons()
                if event.key in (pygame.K_UP, pygame.K_DOWN) and buttons:
                    self.menu_index = (self.menu_index + (-1 if event.key == pygame.K_UP else 1)) % len(buttons)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and buttons:
                    self.activate(buttons[self.menu_index][2])
                elif event.key == pygame.K_r and state in ("over", "won"):
                    self.start()
                elif state == "history" and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.activate("previous" if event.key == pygame.K_LEFT else "next")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            point = self.logical_point(event.pos)
            if point is not None:
                for index, (rect, _, action) in enumerate(self.buttons()):
                    if rect.collidepoint(point):
                        self.menu_index = index
                        self.activate(action)
                        return

    def update(self, dt):
        dt = min(dt, 0.1)
        if self.game.state == "countdown":
            self.countdown = max(0, self.countdown - dt)
            if self.countdown <= 1e-8:
                self.game.state = "playing"
                self.round_active = True
            return
        if self.game.state != "playing":
            return
        self.duration += dt
        self.speed_notice = max(0, self.speed_notice - dt)
        self.elapsed += dt
        interval = 1 / speed_for(self.game.difficulty, self.game.score)
        while self.elapsed + 1e-8 >= interval and self.game.state == "playing":
            self.elapsed -= interval
            old_speed = speed_for(self.game.difficulty, self.game.score)
            self.game.step()
            if speed_for(self.game.difficulty, self.game.score) > old_speed:
                self.speed_notice = 2.5
            if self.game.state in ("over", "won"):
                self.finish(self.game.state)
            interval = 1 / speed_for(self.game.difficulty, self.game.score)

    def text(self, message, position, font=None, color=(235, 235, 235)):
        self.canvas.blit((font or self.font).render(message, True, color), position)

    def draw_buttons(self):
        for index, (rect, label, action) in enumerate(self.buttons()):
            selected = index == self.menu_index
            pygame.draw.rect(self.canvas, (195, 40, 40) if selected or action in ("play", "resume") else (38, 38, 38), rect, border_radius=6)
            if selected:
                pygame.draw.polygon(self.canvas, (255, 255, 255), [(rect.x + 16, rect.centery - 5), (rect.x + 16, rect.centery + 5), (rect.x + 23, rect.centery)])
            self.text(label, (rect.x + 36, rect.centery - 9))

    def draw_scores(self):
        history = self.game.state == "history"
        scores = self.profile["scores"][self.view_mode]
        self.text("Histórico" if history else "Top 5", (48, 110), self.title_font)
        rows = scores["history"]
        if history:
            pages = max(1, math.ceil(len(rows) / 5))
            average = sum(row["score"] for row in rows) / len(rows) if rows else 0
            self.text(f"Últimas {len(rows)} partidas · Média {average:.1f} · Página {self.history_page + 1}/{pages}", (48, 234), self.small_font, (160, 160, 160))
            rows = rows[self.history_page * 5:(self.history_page + 1) * 5]
        else:
            self.text(f"Recorde: {scores['record']} · Melhores partidas deste modo", (48, 234), self.small_font, (160, 160, 160))
            rows = scores["best"]
        if not rows:
            self.text("Nenhuma partida neste modo ainda.", (60, 350))
            self.text("Jogue para registrar sua pontuação.", (60, 385), self.small_font, (160, 160, 160))
            return
        for label, x in [("PONTOS", 80), ("DATA", 238), ("TEMPO", 450)]:
            self.text(label, (x, 270), self.small_font, (160, 160, 160))
        for index, row in enumerate(rows):
            y = 300 + index * 48
            pygame.draw.rect(self.canvas, (26, 26, 26) if index % 2 == 0 else (18, 18, 18), (48, y - 7, 504, 45))
            timestamp = datetime.fromisoformat(row["date"])
            date = f"{timestamp.day:02}/{timestamp.month:02}/{timestamp.year % 100:02} {timestamp.hour:02}:{timestamp.minute:02}"
            seconds = int(row["duration"])
            self.text(f"{index + 1 + (self.history_page * 5 if history else 0):02}", (55, y), self.small_font, (160, 160, 160))
            self.text(str(row["score"]), (90, y))
            self.text(date, (238, y), self.small_font)
            self.text(f"{seconds // 60}:{seconds % 60:02}", (450, y), self.small_font)
            status = {"over": "Concluída", "won": "Tabuleiro completo", "interrupted": "Interrompida"}[row["result"]]
            self.text(status, (238, y + 20), self.small_font, (150, 150, 150))

    def draw(self):
        state = self.game.state
        self.canvas.fill((12, 12, 12))
        pygame.draw.rect(self.canvas, (24, 24, 24), (0, 0, BOARD_SIZE, HEADER))
        self.text("SNAKE", (24, 12), self.brand_font)
        mode = self.game.difficulty if state in ("playing", "countdown", "paused", "over", "won") else self.profile["settings"]["difficulty"]
        if state in ("ranking", "history"):
            mode = self.view_mode
        self.text(DIFFICULTIES[mode][0] + " · Jogo local", (24, 46), self.small_font, (150, 150, 150))
        if state in ("playing", "countdown", "paused", "over", "won"):
            self.text(f"Pontos: {self.game.score}", (300, 27))
        self.text(f"Recorde: {self.profile['scores'][mode]['record']}", (440, 27), self.small_font)
        for x in range(0, BOARD_SIZE, CELL):
            pygame.draw.line(self.canvas, (25, 25, 25), (x, HEADER), (x, HEADER + BOARD_SIZE))
        for y in range(HEADER, HEADER + BOARD_SIZE, CELL):
            pygame.draw.line(self.canvas, (25, 25, 25), (0, y), (BOARD_SIZE, y))
        show_entities = state in ("playing", "countdown", "paused")
        if show_entities and self.game.apple is not None:
            x, y = self.game.apple
            pygame.draw.rect(self.canvas, (235, 62, 62), (x * CELL + 2, HEADER + y * CELL + 4, CELL - 4, CELL - 6), border_radius=4)
            pygame.draw.rect(self.canvas, (170, 170, 170), (x * CELL + 9, HEADER + y * CELL + 1, 3, 4))
        for x, y in self.game.snake if show_entities else []:
            pygame.draw.rect(self.canvas, (240, 240, 240), (x * CELL + 1, HEADER + y * CELL + 1, CELL - 2, CELL - 2), border_radius=3)
        head_x, head_y = self.game.snake[0]
        dx, dy = self.game.direction
        for side in (-1, 1) if show_entities else []:
            eye = (head_x * CELL + CELL // 2 + dx * 5 - dy * side * 4,
                   HEADER + head_y * CELL + CELL // 2 + dy * 5 + dx * side * 4)
            pygame.draw.circle(self.canvas, (12, 12, 12), eye, 2)
        footer = "SETAS: mover · P: pausa · F11: tela cheia" if state == "playing" else "SETAS: menu · ENTER: escolher · ESC: voltar"
        if state == "ready":
            footer = "SETAS / MOUSE: menu · ENTER: escolher · ESC: sair"
        elif state in ("countdown", "paused"):
            footer = "P / ESC: " + ("retomar" if state == "paused" else "pausar") + " · F11: tela cheia"
        if state == "playing" and self.speed_notice > 0:
            footer = f"Ritmo aumentado: {speed_for(self.game.difficulty, self.game.score)} movimentos/s"
        self.text(footer, (24, HEADER + BOARD_SIZE + 12), self.small_font, (170, 170, 170))
        if state != "playing":
            overlay = pygame.Surface((BOARD_SIZE, BOARD_SIZE), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 210))
            self.canvas.blit(overlay, (0, HEADER))
            if state == "ready":
                self.text("Snake Game", (60, 165), self.title_font)
                self.text("Colete maçãs e evite as paredes e o corpo.", (60, 228), color=(160, 160, 160))
                self.text("Pontuações salvas por dificuldade.", (60, 265), self.small_font, (160, 160, 160))
            elif state == "settings":
                self.text("Configurações", (60, 150), self.title_font)
                self.text("Fácil · Normal · Difícil", (60, 215), color=(160, 160, 160))
                self.text("Preferências salvas automaticamente.", (60, 250), self.small_font, (160, 160, 160))
            elif state == "paused":
                self.text("Jogo pausado", (60, 180), self.title_font)
                self.text("O jogo espera por você. P ou Esc para retomar.", (60, 246), self.small_font, (160, 160, 160))
            elif state == "countdown":
                self.text("Prepare-se.", (60, 215), self.title_font)
                self.text(str(max(1, math.ceil(self.countdown))), (265, 294), self.number_font, (235, 62, 62))
                self.text("P ou Esc pausa a contagem.", (60, 427), color=(160, 160, 160))
            elif state in ("over", "won"):
                self.text("Tabuleiro completo!" if state == "won" else "Fim de jogo.", (60, 145), self.title_font)
                self.text(f"Modo {DIFFICULTIES[self.game.difficulty][0]}", (60, 208), color=(160, 160, 160))
                self.text(str(self.game.score), (60, 250), self.number_font)
                self.text("maçãs coletadas", (60, 330), color=(160, 160, 160))
                seconds = int(self.duration)
                self.text(f"Tempo: {seconds // 60}:{seconds % 60:02}", (60, 365))
                self.text(f"Recorde: {self.profile['scores'][self.game.difficulty]['record']}", (310, 365))
                if self.new_record:
                    self.text("NOVO RECORDE!", (60, 420), color=(235, 62, 62))
            else:
                self.draw_scores()
            self.draw_buttons()
        if self.notice:
            pygame.draw.rect(self.canvas, (24, 24, 24), (0, 652, BOARD_SIZE, 22))
            self.text(self.notice, (24, 653), self.small_font, (235, 100, 100))
        area = self.scene_geometry()
        self.screen.fill((5, 5, 5))
        self.screen.blit(pygame.transform.scale(self.canvas, area.size), area)
        pygame.display.flip()

    def run(self):
        try:
            while self.running:
                dt = self.clock.tick(60) / 1000
                for event in pygame.event.get():
                    self.handle_event(event)
                if self.running:
                    self.update(dt)
                    self.draw()
        finally:
            pygame.quit()


def check_build(output):
    """Confere o pacote sem janela, usando somente dados da pasta indicada."""
    output.mkdir(parents=True, exist_ok=True)
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    app = App(output / "profile.json")
    try:
        def capture(filename):
            app.draw()
            pygame.image.save(app.screen, str(output / filename))
        capture("menu.png")
        app.start()
        capture("contagem.png")
        for _ in range(30):
            app.update(0.1)
        assert app.game.state == "playing"
        app.game.snake = [(15, 15), (16, 15), (17, 15), (17, 16), (18, 16)]
        app.game.score, app.duration = 12, 75.0
        app.game.apple = (10, 12)
        capture("partida.png")
        app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
        initial = app.game.snake.copy(), app.duration
        app.update(0.1)
        assert initial == (app.game.snake, app.duration)
        capture("pausa.png")
        app.game.state = "over"
        app.finish("over")
        assert load_profile(app.profile_path)["scores"][app.game.difficulty]["record"] == 12
        capture("resultado.png")
        for state in ("ranking", "history", "settings"):
            app.activate(state)
            capture(state + ".png")
        app.handle_event(pygame.event.Event(pygame.VIDEORESIZE, w=900, h=540))
        app.draw()
        assert app.logical_point((-1, -1)) is None
        (output / "result.json").write_text(json.dumps({"ok": True, "history": True, "pause": True, "countdown": True, "resize": True}), encoding="utf-8")
    finally:
        pygame.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snake Game")
    parser.add_argument("--check-build", type=Path, metavar="PASTA")
    args = parser.parse_args()
    if args.check_build:
        try:
            check_build(args.check_build)
        except Exception as error:
            args.check_build.mkdir(parents=True, exist_ok=True)
            (args.check_build / "result.json").write_text(json.dumps({"ok": False, "error": str(error)}), encoding="utf-8")
            raise SystemExit(1)
    else:
        App().run()

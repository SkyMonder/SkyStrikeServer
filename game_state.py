# game_state.py
# Серверная логика SkyStrike
# Версия 0.6.3 — таймаут помечает игрока мёртвым, а не удаляет
# Упрощённая проверка выстрела (без стен) для отладки

import math
import time
import random
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from shared import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------- Карта и константы -----------------------------
MAP = [
    "1111111111111111",
    "1000000000000001",
    "1011110011110101",
    "1010010010010101",
    "1010010010010101",
    "1011110011110101",
    "1000000000000001",
    "1011111111110101",
    "1010000000000101",
    "1010111111100101",
    "1010100000100101",
    "1010101110100101",
    "1010100010100101",
    "1010111111100101",
    "1000000000000001",
    "1111111111111111"
]
MAP_WIDTH, MAP_HEIGHT = len(MAP[0]), len(MAP)
BOMB_SITES = [(2.5, 7.5), (13.5, 7.5)]
SPAWNS = {'T': [(1.5, 1.5)], 'CT': [(8.5, 8.5)]}

def is_wall(x: float, y: float) -> bool:
    mx, my = int(math.floor(x)), int(math.floor(y))
    if mx < 0 or my < 0 or mx >= MAP_WIDTH or my >= MAP_HEIGHT:
        return True
    return MAP[my][mx] == '1'

def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)

# ----------------------------- Классы -----------------------------
@dataclass
class Player:
    id: int
    name: str
    team: str
    x: float
    y: float
    angle: float
    health: int = MAX_HEALTH
    ammo: int = MAX_AMMO
    max_ammo: int = MAX_AMMO
    reloading: bool = False
    reload_timer: float = 0.0
    alive: bool = True
    last_shot_time: float = 0.0
    kills: int = 0
    deaths: int = 0
    last_action_time: float = field(default_factory=time.time)
    paused: bool = False
    inputs: dict = field(default_factory=lambda: {
        'forward': False, 'backward': False,
        'left': False, 'right': False,
        'mouse_dx': 0.0, 'mouse_dy': 0.0,
        'shoot': False, 'bomb': False,
        'defuse': False, 'reload': False,
        'paused': False
    })

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'team': self.team,
            'x': self.x,
            'y': self.y,
            'angle': self.angle,
            'health': self.health,
            'ammo': self.ammo,
            'max_ammo': self.max_ammo,
            'reloading': self.reloading,
            'alive': self.alive,
            'kills': self.kills,
            'deaths': self.deaths,
            'paused': self.paused
        }

@dataclass
class Bomb:
    status: str = 'none'
    x: float = 0.0
    y: float = 0.0
    timer: float = 0.0
    planter_id: Optional[int] = None
    defusing: bool = False
    defuser_id: Optional[int] = None
    defuse_timer: float = 0.0

    def to_dict(self) -> dict:
        return {
            'status': self.status,
            'x': self.x,
            'y': self.y,
            'timer': self.timer
        }

@dataclass
class Round:
    phase: str = 'playing'
    time_left: float = ROUND_TIME
    winner: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'phase': self.phase,
            'time_left': self.time_left,
            'winner': self.winner
        }

# ----------------------------- Основное состояние игры -----------------------------
class GameState:
    def __init__(self):
        self.players: Dict[int, Player] = {}
        self.next_id = 1
        self.bomb = Bomb()
        self.round = Round()
        self.round_end_time = 0.0
        self.wins_T = 0
        self.wins_CT = 0
        logger.info("GameState инициализирован")

    # ----------------------------- Игроки -----------------------------
    def add_player(self, name: str, team: str) -> Optional[Player]:
        if team not in ('T', 'CT'):
            t = sum(1 for p in self.players.values() if p.team == 'T' and p.alive)
            ct = sum(1 for p in self.players.values() if p.team == 'CT' and p.alive)
            team = 'T' if t <= ct else 'CT'
        spawns = SPAWNS[team]
        x, y = random.choice(spawns)
        for _ in range(10):
            if not any(distance(p.x, p.y, x, y) < 1.0 for p in self.players.values() if p.alive):
                break
            x, y = random.choice(spawns)
        player = Player(
            id=self.next_id,
            name=name,
            team=team,
            x=x, y=y,
            angle=random.uniform(0, 2 * math.pi)
        )
        self.players[self.next_id] = player
        self.next_id += 1
        logger.info(f"Добавлен игрок {name} (команда {team}), всего: {len(self.players)}")
        return player

    def remove_player(self, player_id: int):
        if player_id in self.players:
            del self.players[player_id]
            logger.info(f"Игрок {player_id} удалён, осталось: {len(self.players)}")

    def get_player(self, pid: int) -> Optional[Player]:
        return self.players.get(pid)

    # ----------------------------- Основной цикл обновления -----------------------------
    def update(self, dt: float):
        now = time.time()

        # ----- Таймаут: помечаем игрока мёртвым, а не удаляем -----
        for pid, p in list(self.players.items()):
            if p.paused:
                continue
            if now - p.last_action_time > 5.0:
                logger.info(f"Игрок {p.name} (ID {pid}) отключён по таймауту, помечаем мёртвым")
                p.alive = False
                # Не удаляем, чтобы сохранить состояние для логики раунда

        # ----- Обновление раунда -----
        if self.round.phase == 'playing':
            self.round.time_left -= dt
            if self.round.time_left <= 0:
                self.round.time_left = 0
                winner = 'CT' if self.bomb.status != 'planted' else 'T'
                self.end_round(winner)

        # ----- Обновление бомбы -----
        if self.bomb.status == 'planted':
            self.bomb.timer -= dt
            if self.bomb.timer <= 0:
                self.bomb.timer = 0
                self.bomb.status = 'exploded'
                self.end_round('T')
            if self.bomb.defusing:
                self.bomb.defuse_timer -= dt
                if self.bomb.defuse_timer <= 0:
                    self.bomb.status = 'defused'
                    self.bomb.defusing = False
                    self.end_round('CT')

        # ----- Обновление игроков -----
        for player in self.players.values():
            if not player.alive:
                continue

            inputs = player.inputs
            player.paused = inputs.get('paused', False)
            if player.paused:
                continue

            # Перезарядка
            if player.reloading:
                player.reload_timer -= dt
                if player.reload_timer <= 0:
                    player.reloading = False
                    player.ammo = player.max_ammo

            # Поворот
            if inputs['mouse_dx'] != 0:
                player.angle += inputs['mouse_dx'] * 2.0 * dt * 10
                player.angle %= 2 * math.pi

            # Движение
            dx, dy = 0.0, 0.0
            if inputs['forward']:
                dx += math.cos(player.angle)
                dy += math.sin(player.angle)
            if inputs['backward']:
                dx -= math.cos(player.angle)
                dy -= math.sin(player.angle)
            if inputs['left']:
                dx += math.cos(player.angle - math.pi/2)
                dy += math.sin(player.angle - math.pi/2)
            if inputs['right']:
                dx += math.cos(player.angle + math.pi/2)
                dy += math.sin(player.angle + math.pi/2)

            length = math.hypot(dx, dy)
            if length > 0:
                dx /= length
                dy /= length
                speed = PLAYER_SPEED
                new_x = player.x + dx * speed * dt
                new_y = player.y + dy * speed * dt

                if not is_wall(new_x, player.y) and not self.collides_with_players(new_x, player.y, player.id):
                    player.x = new_x
                if not is_wall(player.x, new_y) and not self.collides_with_players(player.x, new_y, player.id):
                    player.y = new_y

            # Стрельба (упрощённая версия – без проверки стены)
            if (inputs['shoot'] and not player.reloading and player.ammo > 0 and
                (now - player.last_shot_time) >= SHOT_COOLDOWN):
                player.last_shot_time = now
                player.ammo -= 1
                self.process_shot(player)

            # Установка бомбы
            if inputs['bomb'] and player.team == 'T' and self.bomb.status == 'none' and player.alive:
                for site_x, site_y in BOMB_SITES:
                    if distance(player.x, player.y, site_x, site_y) < 1.0:
                        self.plant_bomb(player.id, site_x, site_y)
                        break

            # Обезвреживание
            if inputs['defuse'] and player.team == 'CT' and self.bomb.status == 'planted' and player.alive:
                if not self.bomb.defusing:
                    if distance(player.x, player.y, self.bomb.x, self.bomb.y) < 1.0:
                        self.bomb.defusing = True
                        self.bomb.defuser_id = player.id
                        self.bomb.defuse_timer = BOMB_DEFUSE_TIME

            # Перезарядка
            if inputs['reload'] and not player.reloading and player.ammo < player.max_ammo:
                player.reloading = True
                player.reload_timer = RELOAD_TIME

        # Проверка окончания раунда
        self.check_round_end()

        # Авторесет через 5 секунд
        if self.round.phase == 'ended':
            if self.round_end_time == 0:
                self.round_end_time = time.time()
            elif time.time() - self.round_end_time > 5.0:
                logger.info("Автоматический ресет раунда")
                self.reset_round()

    # ----------------------------- Вспомогательные методы -----------------------------
    def collides_with_players(self, x: float, y: float, exclude_id: int) -> bool:
        for pid, p in self.players.items():
            if pid == exclude_id or not p.alive:
                continue
            if distance(x, y, p.x, p.y) < 0.6:
                return True
        return False

    # Упрощённый метод выстрела (без проверки стен, но с проверкой расстояния и угла)
    def process_shot(self, shooter: Player):
        logger.info(f"=== ВЫСТРЕЛ ОТ {shooter.id} ({shooter.name}) ===")
        logger.info(f"Позиция: ({shooter.x:.2f}, {shooter.y:.2f}), угол: {math.degrees(shooter.angle):.1f}°")
        
        max_dist = MAX_DEPTH
        half_fov = math.radians(35)  # половина FOV (70°)
        hit_player = None
        hit_distance = max_dist
        hit_head = False

        for pid, target in self.players.items():
            if pid == shooter.id or not target.alive:
                continue

            # Расстояние до цели
            dist = distance(shooter.x, shooter.y, target.x, target.y)
            if dist > max_dist:
                continue

            # Угол до цели
            angle_to_target = math.atan2(target.y - shooter.y, target.x - shooter.x)
            diff = angle_to_target - shooter.angle
            diff = (diff + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) > half_fov:
                continue

            # Проверяем, что между ними нет стены (опционально – можно закомментировать)
            # wall_dist = self.cast_ray(shooter.x, shooter.y, shooter.angle)
            # if wall_dist < dist:
            #     continue

            # Попадание в тело
            if self.line_circle_intersect(shooter.x, shooter.y,
                                          shooter.x + math.cos(shooter.angle)*dist,
                                          shooter.y + math.sin(shooter.angle)*dist,
                                          target.x, target.y, PLAYER_RADIUS):
                if dist < hit_distance:
                    hit_distance = dist
                    hit_player = target
                    hit_head = False

            # Попадание в голову (смещена вперёд)
            head_x = target.x + math.cos(target.angle) * 0.15
            head_y = target.y + math.sin(target.angle) * 0.15
            if self.line_circle_intersect(shooter.x, shooter.y,
                                          shooter.x + math.cos(shooter.angle)*dist,
                                          shooter.y + math.sin(shooter.angle)*dist,
                                          head_x, head_y, HEAD_RADIUS):
                dist_to_head = distance(shooter.x, shooter.y, head_x, head_y)
                if dist_to_head < hit_distance:
                    hit_distance = dist_to_head
                    hit_player = target
                    hit_head = True

        if hit_player:
            damage = HEAD_DAMAGE if hit_head else BODY_DAMAGE
            hit_player.health -= damage
            logger.info(f"ПОПАДАНИЕ! Нанесён урон {damage}, здоровье цели: {hit_player.health}")
            if hit_player.health <= 0:
                hit_player.health = 0
                hit_player.alive = False
                hit_player.deaths += 1
                shooter.kills += 1
                logger.info(f"Игрок {hit_player.name} убит")
        else:
            logger.info("Никто не попал")

    def line_circle_intersect(self, x1, y1, x2, y2, cx, cy, r) -> bool:
        dx = x2 - x1
        dy = y2 - y1
        fx = x1 - cx
        fy = y1 - cy
        a = dx*dx + dy*dy
        b = 2*(fx*dx + fy*dy)
        c = fx*fx + fy*fy - r*r
        disc = b*b - 4*a*c
        if disc < 0:
            return False
        disc = math.sqrt(disc)
        t1 = (-b - disc) / (2*a)
        t2 = (-b + disc) / (2*a)
        return (0 <= t1 <= 1) or (0 <= t2 <= 1)

    def cast_ray(self, x, y, angle) -> float:
        # Оставлен для возможного использования, но в process_shot мы его не вызываем
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)
        step_x = 1 if cos_a >= 0 else -1
        step_y = 1 if sin_a >= 0 else -1
        if cos_a != 0:
            delta_dist_x = abs(1 / cos_a)
            if cos_a > 0:
                dist_x = (math.floor(x) + 1 - x) * delta_dist_x
            else:
                dist_x = (x - math.floor(x)) * delta_dist_x
        else:
            delta_dist_x = float('inf')
            dist_x = float('inf')
        if sin_a != 0:
            delta_dist_y = abs(1 / sin_a)
            if sin_a > 0:
                dist_y = (math.floor(y) + 1 - y) * delta_dist_y
            else:
                dist_y = (y - math.floor(y)) * delta_dist_y
        else:
            delta_dist_y = float('inf')
            dist_y = float('inf')
        cur_x, cur_y = x, y
        for _ in range(MAX_DEPTH * 2):
            if dist_x < dist_y:
                dist_x += delta_dist_x
                cur_x += step_x * delta_dist_x
            else:
                dist_y += delta_dist_y
                cur_y += step_y * delta_dist_y
            mx = int(math.floor(cur_x))
            my = int(math.floor(cur_y))
            if mx < 0 or my < 0 or mx >= MAP_WIDTH or my >= MAP_HEIGHT:
                return MAX_DEPTH
            if MAP[my][mx] == '1':
                return distance(x, y, cur_x, cur_y)
        return MAX_DEPTH

    def plant_bomb(self, player_id: int, site_x: float, site_y: float):
        if self.bomb.status == 'none':
            self.bomb.status = 'planted'
            self.bomb.x, self.bomb.y = site_x, site_y
            self.bomb.timer = BOMB_EXPLODE_TIME
            self.bomb.planter_id = player_id
            self.bomb.defusing = False
            self.bomb.defuser_id = None
            logger.info(f"Бомба установлена на ({site_x}, {site_y}) игроком {player_id}")

    def end_round(self, winner: str):
        if self.round.phase == 'ended':
            return
        self.round.phase = 'ended'
        self.round.winner = winner
        self.round_end_time = 0.0
        if winner == 'T':
            self.wins_T += 1
        else:
            self.wins_CT += 1
        logger.info(f"Раунд окончен, победитель {winner}")

    def check_round_end(self):
        if self.round.phase == 'ended':
            return
        alive_players = [p for p in self.players.values() if p.alive]
        if len(alive_players) < 2:
            return
        alive_t = [p for p in alive_players if p.team == 'T']
        alive_ct = [p for p in alive_players if p.team == 'CT']
        if not alive_t:
            self.end_round('CT')
        elif not alive_ct:
            self.end_round('T')

    def reset_round(self):
        self.round.phase = 'playing'
        self.round.time_left = ROUND_TIME
        self.round.winner = None
        self.round_end_time = 0.0
        self.bomb.status = 'none'
        self.bomb.defusing = False
        self.bomb.defuser_id = None
        self.bomb.planter_id = None
        for player in self.players.values():
            player.alive = True
            player.health = MAX_HEALTH
            player.ammo = MAX_AMMO
            player.reloading = False
            player.reload_timer = 0.0
            spawns = SPAWNS[player.team]
            x, y = random.choice(spawns)
            player.x, player.y = x, y
            player.angle = random.uniform(0, 2 * math.pi)
        logger.info("Раунд сброшен")

    def get_state(self, player_id: int) -> dict:
        p = self.get_player(player_id)
        if not p:
            return {}
        others = [pl.to_dict() for pid, pl in self.players.items() if pid != player_id]
        return {
            'player': p.to_dict(),
            'players': others,
            'bomb': self.bomb.to_dict(),
            'round': self.round.to_dict(),
            'wins_T': self.wins_T,
            'wins_CT': self.wins_CT
        }

    def get_stats(self) -> dict:
        return {
            'total_players': len(self.players),
            'alive_players': sum(1 for p in self.players.values() if p.alive),
            'round_phase': self.round.phase,
            'round_time_left': self.round.time_left,
            'bomb_status': self.bomb.status,
            'wins_T': self.wins_T,
            'wins_CT': self.wins_CT
        }

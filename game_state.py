#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SkyStrike Game State Module
Версия: 0.2
Зависимости: нет (используется только стандартная библиотека)
Назначение: содержит классы Player, Bomb, Round, GameState и вспомогательные функции
для управления состоянием матча, коллизиями, стрельбой, бомбой и логикой раунда.
"""

import math
import time
import random
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ----------------------------- Игровые константы -----------------------------
# Карта (1 – стена, 0 – пол)
MAP = [
    "1111111111",
    "1000000001",
    "1001110001",
    "1001000001",
    "1001000001",
    "1000000001",
    "1000111001",
    "1000000001",
    "1000000001",
    "1111111111"
]
MAP_WIDTH = len(MAP[0])
MAP_HEIGHT = len(MAP)

# Позиции спавнов (команда -> список координат)
SPAWNS = {
    'T': [(1.5, 1.5)],
    'CT': [(8.5, 8.5)]
}

# Точки для установки бомбы
BOMB_SITES = [(3.5, 3.5), (6.5, 6.5)]

# Физика и боевые параметры
PLAYER_RADIUS = 0.3
HEAD_RADIUS = 0.12
PLAYER_SPEED = 2.5
ROTATION_SPEED = 2.0          # радиан/сек (чувствительность мыши)
SHOT_COOLDOWN = 0.3           # секунд между выстрелами
RELOAD_TIME = 2.0
BOMB_PLANT_TIME = 3.0         # (не используется в update, оставлено для справки)
BOMB_DEFUSE_TIME = 5.0
BOMB_EXPLODE_TIME = 40.0      # время до взрыва после установки
ROUND_TIME = 120.0            # длительность раунда в секундах
BODY_DAMAGE = 20
HEAD_DAMAGE = 60
MAX_HEALTH = 100
MAX_AMMO = 30
MAX_DEPTH = 20                # дальность луча для стрельбы
MAX_SPEED = PLAYER_SPEED * 1.2 # античит: допустимое превышение скорости


# ----------------------------- Вспомогательные функции -----------------------------
def is_wall(x: float, y: float) -> bool:
    """Проверяет, является ли клетка с координатами (x, y) стеной."""
    mx = int(math.floor(x))
    my = int(math.floor(y))
    if mx < 0 or my < 0 or mx >= MAP_WIDTH or my >= MAP_HEIGHT:
        return True
    return MAP[my][mx] == '1'


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Евклидово расстояние между двумя точками."""
    return math.hypot(x2 - x1, y2 - y1)


def point_in_circle(px: float, py: float, cx: float, cy: float, radius: float) -> bool:
    """Проверяет, находится ли точка (px, py) внутри круга с центром (cx, cy) и радиусом radius."""
    return distance(px, py, cx, cy) <= radius


def line_circle_intersect(x1: float, y1: float, x2: float, y2: float,
                          cx: float, cy: float, r: float) -> bool:
    """
    Проверяет пересечение отрезка (x1,y1)-(x2,y2) с окружностью (cx,cy,r).
    Используется для определения попадания луча в хитбокс игрока.
    """
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


# ----------------------------- Классы состояния -----------------------------
@dataclass
class Player:
    """Игрок."""
    id: int
    name: str
    team: str                # 'T' или 'CT'
    x: float
    y: float
    angle: float             # направление взгляда в радианах
    health: int = MAX_HEALTH
    ammo: int = MAX_AMMO
    max_ammo: int = MAX_AMMO
    reloading: bool = False
    reload_timer: float = 0.0
    alive: bool = True
    last_shot_time: float = 0.0
    # Ввод от клиента (обновляется каждый кадр)
    inputs: dict = field(default_factory=lambda: {
        'forward': False,
        'backward': False,
        'left': False,
        'right': False,
        'mouse_dx': 0.0,
        'mouse_dy': 0.0,
        'shoot': False,
        'bomb': False,
        'defuse': False,
        'reload': False,
    })

    def to_dict(self) -> dict:
        """Преобразует состояние игрока в словарь для отправки клиенту."""
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
        }


@dataclass
class Bomb:
    """Состояние бомбы."""
    status: str = 'none'          # 'none', 'planted', 'exploded', 'defused'
    x: float = 0.0
    y: float = 0.0
    timer: float = 0.0            # оставшееся время до взрыва
    planter_id: Optional[int] = None
    defusing: bool = False
    defuser_id: Optional[int] = None
    defuse_timer: float = 0.0

    def to_dict(self) -> dict:
        return {
            'status': self.status,
            'x': self.x,
            'y': self.y,
            'timer': self.timer,
        }


@dataclass
class Round:
    """Состояние раунда."""
    phase: str = 'playing'        # 'playing', 'ended'
    time_left: float = ROUND_TIME
    winner: Optional[str] = None  # 'T' или 'CT'

    def to_dict(self) -> dict:
        return {
            'phase': self.phase,
            'time_left': self.time_left,
            'winner': self.winner,
        }


# ----------------------------- Основной класс GameState -----------------------------
class GameState:
    """
    Управляет всем состоянием игры: игроками, бомбой, раундом.
    Содержит методы обновления, обработки выстрелов, коллизий, логики бомбы.
    """

    def __init__(self):
        self.players: Dict[int, Player] = {}
        self.next_id = 1
        self.bomb = Bomb()
        self.round = Round()
        self.last_update_time = time.time()
        self.round_end_time = 0.0   # время окончания раунда для авторесета

    def add_player(self, name: str) -> Player:
        """
        Добавляет нового игрока с балансировкой команд.
        Возвращает созданный объект Player.
        """
        t_count = sum(1 for p in self.players.values() if p.team == 'T' and p.alive)
        ct_count = sum(1 for p in self.players.values() if p.team == 'CT' and p.alive)
        team = 'T' if t_count <= ct_count else 'CT'
        spawns = SPAWNS[team]
        x, y = random.choice(spawns)
        # Проверяем, что спавн не занят другим живым игроком
        for _ in range(10):
            occupied = False
            for p in self.players.values():
                if p.alive and distance(p.x, p.y, x, y) < 1.0:
                    occupied = True
                    break
            if not occupied:
                break
            x, y = random.choice(spawns)

        player = Player(
            id=self.next_id,
            name=name,
            team=team,
            x=x,
            y=y,
            angle=random.uniform(0, 2 * math.pi)
        )
        self.players[self.next_id] = player
        self.next_id += 1
        logger.info(f"Игрок {name} (ID {player.id}) добавлен в команду {team}")
        return player

    def get_player(self, player_id: int) -> Optional[Player]:
        """Возвращает игрока по ID или None, если не найден."""
        return self.players.get(player_id)

    def update(self, dt: float):
        """
        Основной шаг обновления состояния игры.
        Вызывается с фиксированным интервалом (например, 50 мс).
        """
        now = time.time()

        # ---------- Обновление раунда ----------
        if self.round.phase == 'playing':
            self.round.time_left -= dt
            if self.round.time_left <= 0:
                self.round.time_left = 0
                # Если бомба не установлена, побеждают CT, иначе T
                winner = 'CT' if self.bomb.status != 'planted' else 'T'
                self.end_round(winner)

        # ---------- Обновление бомбы ----------
        if self.bomb.status == 'planted':
            self.bomb.timer -= dt
            if self.bomb.timer <= 0:
                self.bomb.timer = 0
                self.bomb.status = 'exploded'
                logger.info("Бомба взорвалась!")
                self.end_round('T')

            # Обезвреживание
            if self.bomb.defusing:
                self.bomb.defuse_timer -= dt
                if self.bomb.defuse_timer <= 0:
                    self.bomb.status = 'defused'
                    self.bomb.defusing = False
                    logger.info(f"Бомба обезврежена игроком {self.bomb.defuser_id}")
                    self.end_round('CT')

        # ---------- Обновление игроков ----------
        for player in self.players.values():
            if not player.alive:
                continue

            # Перезарядка
            if player.reloading:
                player.reload_timer -= dt
                if player.reload_timer <= 0:
                    player.reloading = False
                    player.ammo = player.max_ammo
                    logger.debug(f"Игрок {player.id} перезарядился")

            # Движение
            inputs = player.inputs

            # Поворот (горизонтальный)
            if inputs['mouse_dx'] != 0:
                player.angle += inputs['mouse_dx'] * ROTATION_SPEED * dt * 10
                player.angle %= 2 * math.pi   # нормализация

            # Желаемое направление движения
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
                max_move = speed * dt * (MAX_SPEED / PLAYER_SPEED)  # чуть больше допустимого
                new_x = player.x + dx * speed * dt
                new_y = player.y + dy * speed * dt

                # Античит: проверка на телепортацию
                if distance(player.x, player.y, new_x, new_y) > max_move * 1.5:
                    logger.warning(f"Игрок {player.id} попытался телепортироваться, блокируем")
                else:
                    # Коллизии со стенами и другими игроками (раздельно по осям)
                    if not is_wall(new_x, player.y) and not self.collides_with_players(new_x, player.y, player.id):
                        player.x = new_x
                    if not is_wall(player.x, new_y) and not self.collides_with_players(player.x, new_y, player.id):
                        player.y = new_y

            # Стрельба
            if (inputs['shoot'] and not player.reloading and player.ammo > 0 and
                    (now - player.last_shot_time) >= SHOT_COOLDOWN):
                player.last_shot_time = now
                player.ammo -= 1
                self.process_shot(player)
                logger.debug(f"Игрок {player.id} выстрелил, осталось патронов {player.ammo}")

            # Установка бомбы
            if inputs['bomb'] and player.team == 'T' and self.bomb.status == 'none' and player.alive:
                for site_x, site_y in BOMB_SITES:
                    if distance(player.x, player.y, site_x, site_y) < 1.0:
                        self.plant_bomb(player.id, site_x, site_y)
                        logger.info(f"Игрок {player.id} установил бомбу на точке ({site_x}, {site_y})")
                        break

            # Обезвреживание
            if inputs['defuse'] and player.team == 'CT' and self.bomb.status == 'planted' and player.alive:
                if not self.bomb.defusing:
                    if distance(player.x, player.y, self.bomb.x, self.bomb.y) < 1.0:
                        self.bomb.defusing = True
                        self.bomb.defuser_id = player.id
                        self.bomb.defuse_timer = BOMB_DEFUSE_TIME
                        logger.info(f"Игрок {player.id} начал обезвреживание")

            # Перезарядка (по нажатию R)
            if inputs['reload'] and not player.reloading and player.ammo < player.max_ammo:
                player.reloading = True
                player.reload_timer = RELOAD_TIME
                logger.debug(f"Игрок {player.id} начал перезарядку")

        # Проверка окончания раунда по убийству всех
        self.check_round_end()

        # Автоматический ресет раунда через 5 секунд после окончания
        if self.round.phase == 'ended':
            if self.round_end_time == 0:
                self.round_end_time = time.time()
            elif time.time() - self.round_end_time > 5.0:
                logger.info("Автоматический ресет раунда")
                self.reset_round()

    def collides_with_players(self, x: float, y: float, exclude_id: int) -> bool:
        """Проверяет, пересекается ли позиция (x, y) с другими живыми игроками (кроме exclude_id)."""
        for pid, p in self.players.items():
            if pid == exclude_id or not p.alive:
                continue
            if distance(x, y, p.x, p.y) < PLAYER_RADIUS * 2:
                return True
        return False

    def process_shot(self, shooter: Player):
        """
        Обрабатывает выстрел: пускает луч, проверяет попадания в игроков и стены.
        Наносит урон при попадании, учитывая хэдшот.
        """
        ox, oy = shooter.x, shooter.y
        angle = shooter.angle
        max_dist = MAX_DEPTH

        # Расстояние до ближайшей стены
        wall_dist = self.cast_ray(ox, oy, angle)

        # Ищем ближайшего игрока, в которого попали
        hit_player = None
        hit_distance = max_dist
        hit_head = False

        for pid, target in self.players.items():
            if pid == shooter.id or not target.alive:
                continue

            # Проверка попадания в тело (круг)
            if line_circle_intersect(ox, oy, ox + math.cos(angle) * max_dist, oy + math.sin(angle) * max_dist,
                                     target.x, target.y, PLAYER_RADIUS):
                dist_to_target = distance(ox, oy, target.x, target.y)
                if dist_to_target < hit_distance:
                    hit_distance = dist_to_target
                    hit_player = target
                    hit_head = False

            # Проверка попадания в голову (круг смещён вперёд по направлению взгляда цели)
            head_x = target.x + math.cos(target.angle) * 0.15
            head_y = target.y + math.sin(target.angle) * 0.15
            if line_circle_intersect(ox, oy, ox + math.cos(angle) * max_dist, oy + math.sin(angle) * max_dist,
                                     head_x, head_y, HEAD_RADIUS):
                dist_to_head = distance(ox, oy, head_x, head_y)
                if dist_to_head < hit_distance:
                    hit_distance = dist_to_head
                    hit_player = target
                    hit_head = True

        # Если стена ближе, чем игрок, то попадания нет
        if wall_dist < hit_distance:
            return

        if hit_player:
            damage = HEAD_DAMAGE if hit_head else BODY_DAMAGE
            hit_player.health -= damage
            if hit_player.health <= 0:
                hit_player.health = 0
                hit_player.alive = False
                logger.info(f"Игрок {hit_player.id} убит игроком {shooter.id} ({'хэдшот' if hit_head else 'бодишот'})")
            else:
                logger.debug(f"Игроку {hit_player.id} нанесено {damage} урона, осталось {hit_player.health} HP")

    def cast_ray(self, x: float, y: float, angle: float) -> float:
        """
        Простейший raycast для сервера: возвращает расстояние до ближайшей стены
        в направлении angle из точки (x, y). Используется для проверки, не перекрывает ли стена линию выстрела.
        """
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
        """Устанавливает бомбу на указанной точке."""
        if self.bomb.status == 'none':
            self.bomb.status = 'planted'
            self.bomb.x = site_x
            self.bomb.y = site_y
            self.bomb.timer = BOMB_EXPLODE_TIME
            self.bomb.planter_id = player_id
            self.bomb.defusing = False
            self.bomb.defuser_id = None
            logger.info(f"Бомба установлена на ({site_x}, {site_y})")

    def end_round(self, winner: str):
        """Завершает раунд с объявлением победителя."""
        if self.round.phase == 'ended':
            return
        self.round.phase = 'ended'
        self.round.winner = winner
        self.round_end_time = 0.0   # сброс таймера для авторесета
        logger.info(f"Раунд окончен, победитель: {winner}")

    def check_round_end(self):
        """Проверяет, все ли игроки одной команды мертвы. Если да, завершает раунд."""
        if self.round.phase == 'ended':
            return
        alive_t = [p for p in self.players.values() if p.alive and p.team == 'T']
        alive_ct = [p for p in self.players.values() if p.alive and p.team == 'CT']
        if not alive_t:
            self.end_round('CT')
        elif not alive_ct:
            self.end_round('T')

    def reset_round(self):
        """
        Сбрасывает состояние для нового раунда: респавнит всех игроков,
        восстанавливает здоровье, патроны, убирает бомбу и сбрасывает таймеры.
        """
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
        """
        Возвращает полное состояние игры для конкретного игрока:
        его данные, список других игроков, состояние бомбы и раунда.
        """
        player = self.get_player(player_id)
        if not player:
            return {}
        others = []
        for pid, p in self.players.items():
            if pid != player_id:
                others.append(p.to_dict())
        return {
            'player': player.to_dict(),
            'players': others,
            'bomb': self.bomb.to_dict(),
            'round': self.round.to_dict(),
        }

    def get_stats(self) -> dict:
        """Возвращает общую статистику сервера (количество игроков, состояние раунда и т.п.)."""
        total = len(self.players)
        alive = sum(1 for p in self.players.values() if p.alive)
        return {
            'total_players': total,
            'alive_players': alive,
            'round_phase': self.round.phase,
            'round_time_left': self.round.time_left,
            'bomb_status': self.bomb.status,
        }

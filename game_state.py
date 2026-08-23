# game_state.py (отладочная версия, без удаления и проверки уникальности)
import math
import time
import random
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from shared import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Карта (та же, что и раньше)
MAP = [
    "1111111111",
    "1000000001",
    "1011110101",
    "1000010001",
    "1010010101",
    "1010010101",
    "1000010001",
    "1011110101",
    "1000000001",
    "1111111111"
]
MAP_WIDTH, MAP_HEIGHT = len(MAP[0]), len(MAP)
BOMB_SITES = [(2.5, 2.5), (7.5, 7.5)]
SPAWNS = {'T': [(1.5, 1.5)], 'CT': [(8.5, 8.5)]}

def is_wall(x, y):
    mx, my = int(math.floor(x)), int(math.floor(y))
    if mx < 0 or my < 0 or mx >= MAP_WIDTH or my >= MAP_HEIGHT:
        return True
    return MAP[my][mx] == '1'

def distance(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)

@dataclass
class Player:
    id: int
    name: str
    team: str
    x: float
    y: float
    angle: float
    health: int = 100
    ammo: int = 30
    max_ammo: int = 30
    reloading: bool = False
    reload_timer: float = 0.0
    alive: bool = True
    last_shot_time: float = 0.0
    kills: int = 0
    deaths: int = 0
    last_action_time: float = field(default_factory=time.time)
    inputs: dict = field(default_factory=lambda: {
        'forward': False, 'backward': False,
        'left': False, 'right': False,
        'mouse_dx': 0.0, 'mouse_dy': 0.0,
        'shoot': False, 'bomb': False,
        'defuse': False, 'reload': False
    })

    def to_dict(self):
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
            'deaths': self.deaths
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

    def to_dict(self):
        return {'status': self.status, 'x': self.x, 'y': self.y, 'timer': self.timer}

@dataclass
class Round:
    phase: str = 'playing'
    time_left: float = 120.0
    winner: Optional[str] = None

    def to_dict(self):
        return {'phase': self.phase, 'time_left': self.time_left, 'winner': self.winner}

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

    def add_player(self, name: str, team: str) -> Optional[Player]:
        # ВРЕМЕННО ОТКЛЮЧАЕМ ПРОВЕРКУ УНИКАЛЬНОСТИ
        # if any(p.name == name for p in self.players.values()):
        #     return None
        if team not in ('T','CT'):
            t = sum(1 for p in self.players.values() if p.team=='T' and p.alive)
            ct = sum(1 for p in self.players.values() if p.team=='CT' and p.alive)
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
            angle=random.uniform(0, 2*math.pi)
        )
        self.players[self.next_id] = player
        self.next_id += 1
        logger.info(f"ДОБАВЛЕН ИГРОК: {name} ({team}), всего игроков: {len(self.players)}")
        return player

    def remove_player(self, player_id: int):
        if player_id in self.players:
            del self.players[player_id]
            logger.info(f"Игрок {player_id} удалён, осталось: {len(self.players)}")

    def get_player(self, pid):
        return self.players.get(pid)

    def update(self, dt: float):
        # ВРЕМЕННО ОТКЛЮЧАЕМ ТАЙМАУТ
        # now = time.time()
        # for pid, p in list(self.players.items()):
        #     if now - p.last_action_time > 3.0:
        #         logger.info(f"Игрок {p.name} отключён по таймауту")
        #         self.remove_player(pid)

        # Основная логика (раунд, бомба, игроки) – без изменений
        if self.round.phase == 'playing':
            self.round.time_left -= dt
            if self.round.time_left <= 0:
                self.round.time_left = 0
                winner = 'CT' if self.bomb.status != 'planted' else 'T'
                self.end_round(winner)

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

        for player in self.players.values():
            if not player.alive:
                continue
            # Перезарядка, движение, стрельба (оставляем как было, но можно упростить)
            # ... (код из предыдущих версий)

        self.check_round_end()
        if self.round.phase == 'ended':
            if self.round_end_time == 0:
                self.round_end_time = time.time()
            elif time.time() - self.round_end_time > 5.0:
                self.reset_round()

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

    def end_round(self, winner):
        if self.round.phase == 'ended':
            return
        self.round.phase = 'ended'
        self.round.winner = winner
        if winner == 'T':
            self.wins_T += 1
        else:
            self.wins_CT += 1
        self.round_end_time = 0.0
        logger.info(f"Раунд окончен, победитель {winner}")

    def reset_round(self):
        self.round.phase = 'playing'
        self.round.time_left = 120.0
        self.round.winner = None
        self.round_end_time = 0.0
        self.bomb.status = 'none'
        self.bomb.defusing = False
        for p in self.players.values():
            p.alive = True
            p.health = 100
            p.ammo = 30
            p.reloading = False
            p.reload_timer = 0.0
            spawns = SPAWNS[p.team]
            x, y = random.choice(spawns)
            p.x, p.y = x, y
            p.angle = random.uniform(0, 2*math.pi)
        logger.info("Раунд сброшен")

    def get_state(self, player_id):
        p = self.get_player(player_id)
        if not p:
            return {}
        others = [pl.to_dict() for pid, pl in self.players.items() if pid != player_id]
        logger.info(f"Запрос состояния для игрока {p.name}, возвращаем {len(others)} игроков")
        return {
            'player': p.to_dict(),
            'players': others,
            'bomb': self.bomb.to_dict(),
            'round': self.round.to_dict(),
            'wins_T': self.wins_T,
            'wins_CT': self.wins_CT
        }

    def get_stats(self):
        return {
            'total_players': len(self.players),
            'alive_players': sum(1 for p in self.players.values() if p.alive),
            'round_phase': self.round.phase,
            'round_time_left': self.round.time_left,
            'bomb_status': self.bomb.status,
            'wins_T': self.wins_T,
            'wins_CT': self.wins_CT
        }

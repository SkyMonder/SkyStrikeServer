# shared.py
MAX_AMMO = 30
MAX_HEALTH = 100
PLAYER_SPEED = 3.0
SHOT_COOLDOWN = 0.25
RELOAD_TIME = 1.8

WEAPON_DATA = {
    'ak47': {
        'ammo': 30,
        'reload_time': 2.5,
        'damage': 30,
        'fire_rate': 0.1,
        'spread': 0.02,
        'name': 'AK-47',
        'price': 2700,
        'max_ammo': 30
    },
    'deagle': {
        'ammo': 7,
        'reload_time': 2.0,
        'damage': 50,
        'fire_rate': 0.4,
        'spread': 0.01,
        'name': 'Desert Eagle',
        'price': 650,
        'max_ammo': 7
    },
    'm4a1': {
        'ammo': 30,
        'reload_time': 2.2,
        'damage': 25,
        'fire_rate': 0.08,
        'spread': 0.015,
        'name': 'M4A1',
        'price': 3100,
        'max_ammo': 30
    },
    'awp': {
        'ammo': 10,
        'reload_time': 3.0,
        'damage': 100,
        'fire_rate': 0.8,
        'spread': 0.001,
        'name': 'AWP',
        'price': 4750,
        'max_ammo': 10
    }
}
DEFAULT_WEAPON = 'ak47'
# Время раунда (секунды)
ROUND_TIME = 120.0

# Время до взрыва бомбы (секунды)
BOMB_EXPLODE_TIME = 45.0

# Время установки бомбы (секунды)
BOMB_PLANT_TIME = 3.0

# Время обезвреживания бомбы (секунды)
BOMB_DEFUSE_TIME = 5.0

# Максимальная дальность луча (для стрельбы и рейкастинга)
MAX_DEPTH = 25.0

# Радиус игрока (для коллизий)
PLAYER_RADIUS = 0.4

# Радиус головы (для хэдшотов)
HEAD_RADIUS = 0.15

# Урон в голову и в тело
HEAD_DAMAGE = 75
BODY_DAMAGE = 30

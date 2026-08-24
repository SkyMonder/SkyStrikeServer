# shared.py
# Общие константы для клиента и сервера

MAX_AMMO = 30
MAX_HEALTH = 100
PLAYER_SPEED = 3.0
SHOT_COOLDOWN = 0.25
RELOAD_TIME = 1.8

# NEW: параметры для разных видов оружия
WEAPON_DATA = {
    'ak47': {
        'ammo': 30,
        'reload_time': 2.5,
        'damage': 30,
        'fire_rate': 0.1,
        'spread': 0.02,
        'name': 'AK-47'
    },
    'deagle': {
        'ammo': 7,
        'reload_time': 2.0,
        'damage': 50,
        'fire_rate': 0.4,
        'spread': 0.01,
        'name': 'Desert Eagle'
    },
    'm4a1': {
        'ammo': 30,
        'reload_time': 2.2,
        'damage': 25,
        'fire_rate': 0.08,
        'spread': 0.015,
        'name': 'M4A1'
    },
    'awp': {
        'ammo': 10,
        'reload_time': 3.0,
        'damage': 100,
        'fire_rate': 0.8,
        'spread': 0.001,
        'name': 'AWP'
    }
}

# По умолчанию для совместимости
DEFAULT_WEAPON = 'ak47'

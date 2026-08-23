#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SkyStrike Server
Версия: 0.2
Зависимости: aiohttp (pip install aiohttp)
Запуск: python server.py (порт из PORT или 8080)
Добавлено: /heal, /stats, /reset, улучшенная обработка ошибок.
"""

import os
import json
import asyncio
import logging
from aiohttp import web
from game_state import GameState

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Глобальное состояние игры
game = GameState()
UPDATE_INTERVAL = 0.05  # 50 мс


async def game_loop():
    """Фоновый цикл обновления игрового состояния."""
    while True:
        try:
            game.update(UPDATE_INTERVAL)
        except Exception as e:
            logger.error(f"Ошибка в игровом цикле: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)


async def connect_handler(request):
    """Регистрация нового игрока."""
    try:
        data = await request.json()
        name = data.get('name', 'Player')
        if not name:
            name = 'Player'
        name = name[:20]  # ограничение длины
        player = game.add_player(name)
        state = game.get_state(player.id)
        state['player_id'] = player.id
        logger.info(f"Подключение игрока {name} (ID {player.id})")
        return web.json_response(state)
    except Exception as e:
        logger.error(f"Ошибка в /connect: {e}")
        return web.json_response({'error': str(e)}, status=400)


async def action_handler(request):
    """Приём ввода от клиента и возврат состояния."""
    try:
        data = await request.json()
        player_id = data.get('player_id')
        inputs = data.get('inputs', {})
        if player_id is None:
            return web.json_response({'error': 'player_id required'}, status=400)
        player = game.get_player(player_id)
        if not player:
            return web.json_response({'error': 'player not found'}, status=404)
        # Обновляем ввод игрока (перезаписываем)
        player.inputs = inputs
        # Возвращаем состояние
        state = game.get_state(player_id)
        return web.json_response(state)
    except Exception as e:
        logger.error(f"Ошибка в /action: {e}")
        return web.json_response({'error': str(e)}, status=400)


async def state_handler(request):
    """Получение текущего состояния (без отправки действий)."""
    try:
        player_id = request.query.get('player_id')
        if player_id is None:
            return web.json_response({'error': 'player_id required'}, status=400)
        player_id = int(player_id)
        state = game.get_state(player_id)
        if not state:
            return web.json_response({'error': 'player not found'}, status=404)
        return web.json_response(state)
    except Exception as e:
        logger.error(f"Ошибка в /state: {e}")
        return web.json_response({'error': str(e)}, status=400)


async def heal_handler(request):
    """Эндпоинт для keep-alive (проверка работоспособности)."""
    return web.json_response({'status': 'alive', 'timestamp': time.time()})


async def stats_handler(request):
    """Возвращает общую статистику сервера."""
    stats = game.get_stats()
    return web.json_response(stats)


async def reset_handler(request):
    """Принудительный сброс раунда (административный)."""
    try:
        game.reset_round()
        logger.info("Раунд сброшен через /reset")
        return web.json_response({'status': 'ok', 'message': 'round reset'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


async def not_found_handler(request):
    return web.json_response({'error': 'not found'}, status=404)


def main():
    port = int(os.environ.get('PORT', 8080))
    app = web.Application()
    app.router.add_post('/connect', connect_handler)
    app.router.add_post('/action', action_handler)
    app.router.add_get('/state', state_handler)
    app.router.add_get('/heal', heal_handler)
    app.router.add_get('/stats', stats_handler)
    app.router.add_post('/reset', reset_handler)
    app.router.add_get('/{tail:.*}', not_found_handler)  # заглушка для остальных

    # Запуск фоновой задачи обновления
    loop = asyncio.get_event_loop()
    loop.create_task(game_loop())

    logger.info(f"Запуск сервера на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)


if __name__ == '__main__':
    import time  # для heal_handler
    main()

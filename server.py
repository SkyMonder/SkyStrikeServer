#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SkyStrike Server
Версия: 0.6
Зависимости: fastapi, uvicorn (устанавливаются через pip)
Запуск локально: uvicorn server:app --host 0.0.0.0 --port 8080
Для Vercel: экспортируется переменная app.
Эндпоинты: /connect, /action, /state, /heal, /stats, /reset
"""

import os
import time
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from game_state import GameState

# ----------------------------- Логирование -----------------------------
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ----------------------------- Глобальное состояние -----------------------------
game = GameState()
UPDATE_INTERVAL = 0.05   # 50 мс

# ----------------------------- Модели запросов -----------------------------
class ConnectRequest(BaseModel):
    name: str
    team: Optional[str] = None

class ActionRequest(BaseModel):
    player_id: int
    inputs: Dict[str, Any]

# ----------------------------- Lifespan (фоновая задача) -----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запускает фоновый цикл обновления состояния."""
    async def game_loop():
        while True:
            try:
                game.update(UPDATE_INTERVAL)
            except Exception as e:
                logger.error(f"Ошибка в игровом цикле: {e}")
            await asyncio.sleep(UPDATE_INTERVAL)

    task = asyncio.create_task(game_loop())
    logger.info("Сервер запущен, игровой цикл активен")
    yield
    task.cancel()
    logger.info("Сервер останавливается")

# ----------------------------- FastAPI приложение -----------------------------
app = FastAPI(
    title="SkyStrike Server",
    version="0.6",
    lifespan=lifespan
)

# ----------------------------- Эндпоинты -----------------------------
@app.post("/connect")
async def connect_handler(req: ConnectRequest):
    """
    Регистрация нового игрока.
    Принимает имя и команду (T или CT).
    Возвращает состояние игрока, список других игроков, бомбу, раунд и счёт побед.
    """
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Empty name")
    if len(name) > 20:
        name = name[:20]
    player = game.add_player(name, req.team)
    if player is None:
        raise HTTPException(status_code=400, detail="Name already taken")
    state = game.get_state(player.id)
    state['player_id'] = player.id
    logger.info(f"Игрок {name} (команда {player.team}) подключился, ID {player.id}")
    return state

@app.post("/action")
async def action_handler(req: ActionRequest):
    """
    Приём ввода от игрока.
    Обновляет его последнее действие и возвращает текущее состояние.
    """
    player = game.get_player(req.player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    # Обновляем ввод
    player.inputs = req.inputs
    player.last_action_time = time.time()
    state = game.get_state(req.player_id)
    return state

@app.get("/state")
async def state_handler(player_id: int):
    """
    Возвращает состояние игры для указанного игрока (без отправки действий).
    """
    state = game.get_state(player_id)
    if not state:
        raise HTTPException(status_code=404, detail="Player not found")
    return state

@app.get("/heal")
async def heal_handler():
    """
    Эндпоинт для keep‑alive (проверка работоспособности сервера).
    Возвращает статус и временную метку.
    """
    return {"status": "alive", "timestamp": time.time()}

@app.get("/stats")
async def stats_handler():
    """
    Возвращает общую статистику сервера (количество игроков, состояние раунда, счёт побед).
    """
    return game.get_stats()

@app.post("/reset")
async def reset_handler():
    """
    Принудительный сброс раунда (административный).
    """
    try:
        game.reset_round()
        logger.info("Раунд сброшен через /reset")
        return {"status": "ok", "message": "round reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------- Точка входа для локального запуска -----------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SkyStrike Server (FastAPI version for Vercel)
Версия: 0.3
Зависимости: fastapi, uvicorn (для локального запуска)
Запуск локально: uvicorn server:app --reload
Для Vercel: экспортируется переменная app
"""

import os
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from game_state import GameState

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Глобальное состояние игры
game = GameState()
UPDATE_INTERVAL = 0.05  # 50 мс

# ----------------------------- Модели запросов -----------------------------
class ConnectRequest(BaseModel):
    name: Optional[str] = "Player"

class ActionRequest(BaseModel):
    player_id: int
    inputs: Dict[str, Any]

# ----------------------------- Lifespan (фоновая задача) -----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запускает фоновый цикл обновления при старте и останавливает при завершении."""
    async def game_loop():
        while True:
            try:
                game.update(UPDATE_INTERVAL)
            except Exception as e:
                logger.error(f"Ошибка в игровом цикле: {e}")
            await asyncio.sleep(UPDATE_INTERVAL)

    # Запускаем фоновую задачу
    import asyncio
    task = asyncio.create_task(game_loop())
    logger.info("Сервер запущен, игровой цикл активен")
    yield
    # Остановка при завершении
    task.cancel()
    logger.info("Сервер останавливается")

# ----------------------------- FastAPI приложение -----------------------------
app = FastAPI(title="SkyStrike Server", version="0.3", lifespan=lifespan)

# ----------------------------- Эндпоинты -----------------------------
@app.post("/connect")
async def connect_handler(req: ConnectRequest):
    """Регистрация нового игрока."""
    try:
        name = req.name or "Player"
        name = name[:20]
        player = game.add_player(name)
        state = game.get_state(player.id)
        state["player_id"] = player.id
        logger.info(f"Подключение игрока {name} (ID {player.id})")
        return state
    except Exception as e:
        logger.error(f"Ошибка в /connect: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/action")
async def action_handler(req: ActionRequest):
    """Приём ввода от клиента и возврат состояния."""
    try:
        player = game.get_player(req.player_id)
        if not player:
            raise HTTPException(status_code=404, detail="player not found")
        # Обновляем ввод игрока
        player.inputs = req.inputs
        # Возвращаем состояние
        state = game.get_state(req.player_id)
        return state
    except Exception as e:
        logger.error(f"Ошибка в /action: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/state")
async def state_handler(player_id: int):
    """Получение текущего состояния (без отправки действий)."""
    try:
        state = game.get_state(player_id)
        if not state:
            raise HTTPException(status_code=404, detail="player not found")
        return state
    except Exception as e:
        logger.error(f"Ошибка в /state: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/heal")
async def heal_handler():
    """Эндпоинт для keep-alive (проверка работоспособности)."""
    return {"status": "alive", "timestamp": time.time()}

@app.get("/stats")
async def stats_handler():
    """Возвращает общую статистику сервера."""
    return game.get_stats()

@app.post("/reset")
async def reset_handler():
    """Принудительный сброс раунда (административный)."""
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

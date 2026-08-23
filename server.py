# server.py
import os
import time
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from game_state import GameState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

game = GameState()
UPDATE_INTERVAL = 0.05

app = FastAPI()

# Модели запросов
class ConnectReq(BaseModel):
    name: str
    team: Optional[str] = None

class ActionReq(BaseModel):
    player_id: int
    inputs: Dict[str, Any]

# Эндпоинты
@app.post("/connect")
async def connect(req: ConnectReq):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "Empty name")
    player = game.add_player(name, req.team)
    if player is None:
        raise HTTPException(400, "Name already taken")
    state = game.get_state(player.id)
    state['player_id'] = player.id
    logger.info(f"Подключение: {name} (ID {player.id})")
    return state

@app.post("/action")
async def action(req: ActionReq):
    p = game.get_player(req.player_id)
    if not p:
        raise HTTPException(404, "Player not found")
    p.inputs = req.inputs
    p.last_action_time = time.time()
    return game.get_state(req.player_id)

@app.get("/state")
async def state(player_id: int):
    return game.get_state(player_id)

@app.get("/heal")
async def heal():
    return {"status": "alive", "timestamp": time.time()}

@app.get("/stats")
async def stats():
    return game.get_stats()

@app.post("/reset")
async def reset():
    game.reset_round()
    return {"ok": True}

# Фоновый цикл (запускается при старте)
async def game_loop():
    while True:
        try:
            game.update(UPDATE_INTERVAL)
        except Exception as e:
            logger.error(f"Ошибка в игровом цикле: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)

@app.on_event("startup")
async def startup():
    asyncio.create_task(game_loop())
    logger.info("Сервер запущен, игровой цикл активен")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Сервер останавливается")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

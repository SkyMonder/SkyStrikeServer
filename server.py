# server.py
import os, time, logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from game_state import GameState
import asyncio
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
game = GameState()
UPDATE_INTERVAL = 0.05

class ConnectReq(BaseModel):
    name: str
    team: Optional[str] = None

class ActionReq(BaseModel):
    player_id: int
    inputs: Dict[str, Any]

@asynccontextmanager
async def lifespan(app: FastAPI):
    async def loop():
        while True:
            game.update(UPDATE_INTERVAL)
            await asyncio.sleep(UPDATE_INTERVAL)
    task = asyncio.create_task(loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.post("/connect")
async def connect(req: ConnectReq):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "Empty name")
    player = game.add_player(name, req.team)
    if not player:
        raise HTTPException(400, "Name already taken")
    state = game.get_state(player.id)
    state['player_id'] = player.id
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

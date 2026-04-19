"""
SIAOL-PRO Bridge API v1.0
==========================
API REST para comunicação entre IAs via HTTP.
Exposta via túnel público para acesso do MiniMax e Agent-S.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
import os
import requests
from datetime import datetime

app = FastAPI(title="SIAOL-PRO Symbiosis API", version="1.0")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ynfcmmwxfabdkqstsqkr.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


class Message(BaseModel):
    channel: str
    sender: str
    msg_type: str = "data"
    content: str


class AIQuery(BaseModel):
    prompt: str
    model: str = "llama-3.3-70b-versatile"
    max_tokens: int = 1000


@app.get("/")
def root():
    return {
        "system": "SIAOL-PRO Symbiosis Bridge",
        "version": "v12.0",
        "status": "ONLINE",
        "node": "manus_primary",
        "engines": ["groq/llama-3.3-70b", "ollama/qwen2.5:3b"],
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/message")
def post_message(msg: Message):
    """Enviar mensagem para o canal de comunicação."""
    payload = {
        "channel": msg.channel,
        "sender": msg.sender,
        "msg_type": msg.msg_type,
        "content": msg.content,
        "timestamp": datetime.now().isoformat(),
        "read_by": json.dumps([])
    }
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/ai_symbiosis",
        headers=HEADERS, json=payload, timeout=15
    )
    if resp.status_code in [200, 201]:
        return {"status": "sent", "channel": msg.channel}
    raise HTTPException(status_code=500, detail=f"Supabase error: {resp.status_code}")


@app.get("/messages/{channel}")
def get_messages(channel: str, limit: int = 20):
    """Ler mensagens de um canal."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/ai_symbiosis?channel=eq.{channel}&order=timestamp.desc&limit={limit}",
        headers=HEADERS, timeout=15
    )
    if resp.status_code == 200:
        return resp.json()
    raise HTTPException(status_code=500, detail=f"Supabase error: {resp.status_code}")


@app.post("/ai/query")
def ai_query(query: AIQuery):
    """Consultar a IA via Groq (Llama-3.3-70B)."""
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": query.model,
            "messages": [{"role": "user", "content": query.prompt}],
            "max_tokens": query.max_tokens,
            "temperature": 0.3
        },
        timeout=60
    )
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]
    raise HTTPException(status_code=500, detail=f"Groq error: {resp.status_code}")


@app.get("/predictions/{lottery_type}")
def get_predictions(lottery_type: str):
    """Obter últimas predições de uma loteria."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/ai_symbiosis?channel=eq.predictions&content=cs.{lottery_type}&order=timestamp.desc&limit=5",
        headers=HEADERS, timeout=15
    )
    if resp.status_code == 200:
        return resp.json()
    return []


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)

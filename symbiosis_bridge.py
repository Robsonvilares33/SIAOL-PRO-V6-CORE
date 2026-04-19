"""
SIAOL-PRO SYMBIOSIS BRIDGE v1.0
================================
API Bridge para comunicação entre múltiplas IAs:
  - Manus (terminal local)
  - MiniMax Agent (nuvem)
  - Agent-S (GitHub)
  
Usa Supabase como canal de comunicação persistente (pub/sub via tabela).
Cada IA lê e escreve mensagens na tabela 'ai_symbiosis' do Supabase.
"""
import os
import json
import time
import hashlib
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ynfcmmwxfabdkqstsqkr.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "GROQ_API_KEY_PLACEHOLDER")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN_PLACEHOLDER")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5096280712")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

NODE_ID = os.getenv("SYMBIOSIS_NODE_ID", "manus_primary")


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "ERR": "❌", "AI": "🤖",
            "SEND": "📨", "SYNC": "🔄", "LINK": "🔗"}.get(level, "•")
    print(f"[{ts}] {icon} {msg}")


# ===================== SUPABASE CHANNEL =====================
def send_message(channel, content, msg_type="data"):
    """Enviar mensagem para o canal de comunicação via Supabase."""
    payload = {
        "channel": channel,
        "sender": NODE_ID,
        "msg_type": msg_type,
        "content": json.dumps(content) if isinstance(content, dict) else str(content),
        "timestamp": datetime.now().isoformat(),
        "read_by": json.dumps([])
    }
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/ai_symbiosis",
            headers=HEADERS,
            json=payload,
            timeout=15
        )
        if resp.status_code in [200, 201]:
            log(f"Mensagem enviada ao canal '{channel}'", "SEND")
            return True
        else:
            log(f"Erro ao enviar: {resp.status_code} - {resp.text[:200]}", "ERR")
            return False
    except Exception as e:
        log(f"Erro de conexão: {e}", "ERR")
        return False


def read_messages(channel, since=None, limit=20):
    """Ler mensagens de um canal específico."""
    url = f"{SUPABASE_URL}/rest/v1/ai_symbiosis?channel=eq.{channel}&order=timestamp.desc&limit={limit}"
    if since:
        url += f"&timestamp=gte.{since}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            log(f"Erro ao ler: {resp.status_code}", "ERR")
            return []
    except Exception as e:
        log(f"Erro de leitura: {e}", "ERR")
        return []


def share_knowledge(knowledge_type, data):
    """Compartilhar conhecimento com todas as IAs do ecossistema."""
    content = {
        "knowledge_type": knowledge_type,
        "data": data,
        "source": NODE_ID,
        "version": "v12.0"
    }
    return send_message("knowledge_sharing", content, msg_type="knowledge")


def share_predictions(lottery_type, games, metadata):
    """Compartilhar predições geradas para validação cruzada."""
    content = {
        "lottery_type": lottery_type,
        "games": games,
        "metadata": metadata,
        "source": NODE_ID
    }
    return send_message("predictions", content, msg_type="prediction")


def request_validation(lottery_type, games):
    """Solicitar validação cruzada de outra IA."""
    content = {
        "lottery_type": lottery_type,
        "games": games,
        "request_from": NODE_ID,
        "action": "validate_and_improve"
    }
    return send_message("validation_requests", content, msg_type="request")


def get_peer_insights(channel="knowledge_sharing"):
    """Obter insights de outras IAs do ecossistema."""
    messages = read_messages(channel, limit=50)
    insights = [m for m in messages if m.get("sender") != NODE_ID]
    log(f"Obtidos {len(insights)} insights de peers", "SYNC")
    return insights


# ===================== GROQ COLLABORATIVE ANALYSIS =====================
def collaborative_analysis(own_analysis, peer_insights, lottery_type):
    """Usar Groq (70B) para sintetizar análises de múltiplas IAs."""
    log("Análise colaborativa via Groq (Llama-3.3-70B)...", "AI")
    
    prompt = f"""Você é o SIAOL-PRO AGI, coordenador de um ecossistema de múltiplas IAs.

ANÁLISE PRÓPRIA (Manus):
{json.dumps(own_analysis, indent=2, ensure_ascii=False)[:2000]}

INSIGHTS DE OUTRAS IAs:
{json.dumps(peer_insights[:5], indent=2, ensure_ascii=False)[:2000]}

LOTERIA: {lottery_type}

Sintetize todas as análises e retorne um JSON com:
{{"consensus_numbers": [lista dos números mais recomendados por todas as IAs],
"confidence": 0.0-1.0,
"divergences": ["pontos onde as IAs discordam"],
"improvements": ["sugestões de melhoria baseadas na troca de conhecimento"],
"dominant_pattern": "padrão identificado por múltiplas IAs"}}"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "Você é um coordenador de IA. Sintetize análises de múltiplas IAs e retorne APENAS JSON."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.2
            },
            timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()["choices"][0]["message"]["content"]
            log(f"Análise colaborativa concluída ({len(result)} chars)", "AI")
            try:
                js = result[result.find("{"):result.rfind("}") + 1]
                return json.loads(js)
            except:
                return {"raw_response": result}
        else:
            log(f"Groq erro: {resp.status_code}", "ERR")
            return {}
    except Exception as e:
        log(f"Erro na análise colaborativa: {e}", "ERR")
        return {}


# ===================== TELEGRAM NOTIFICATIONS =====================
def notify_telegram(message):
    """Enviar notificação ao Telegram do comandante."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=15
        )
        return resp.status_code == 200
    except:
        return False


# ===================== MAIN BRIDGE LOOP =====================
def run_bridge(mode="listen"):
    """Executar o bridge em modo listen (escuta) ou broadcast (envia)."""
    log(f"SIAOL-PRO Symbiosis Bridge v1.0 - Node: {NODE_ID}", "LINK")
    log(f"Modo: {mode}", "INFO")
    log(f"Canal: Supabase ({SUPABASE_URL})", "LINK")
    log(f"Motor IA: Groq ({GROQ_MODEL})", "AI")
    
    if mode == "listen":
        log("Escutando mensagens de outras IAs...", "SYNC")
        last_check = datetime.now().isoformat()
        while True:
            messages = read_messages("knowledge_sharing", since=last_check)
            for msg in messages:
                if msg.get("sender") != NODE_ID:
                    log(f"Nova mensagem de {msg['sender']}: {msg.get('msg_type')}", "SYNC")
                    # Processar e responder
                    content = json.loads(msg.get("content", "{}"))
                    if msg.get("msg_type") == "request":
                        log("Processando pedido de validação...", "AI")
                        # Usar Groq para validar
                        analysis = collaborative_analysis(
                            content, [], content.get("lottery_type", "megasena")
                        )
                        send_message("validation_responses", analysis, "response")
            last_check = datetime.now().isoformat()
            time.sleep(30)  # Verificar a cada 30 segundos
    
    elif mode == "broadcast":
        log("Enviando dados para o ecossistema...", "SEND")
        # Carregar últimas predições e compartilhar
        import glob
        output_files = glob.glob("/home/ubuntu/SIAOL_LIVE/output_*.json")
        for f in sorted(output_files)[-4:]:  # Últimas 4 loterias
            try:
                with open(f) as fp:
                    data = json.load(fp)
                share_predictions(
                    data.get("lottery_type", "unknown"),
                    data.get("games", []),
                    data.get("metadata", {})
                )
            except Exception as e:
                log(f"Erro ao compartilhar {f}: {e}", "ERR")
        log("Broadcast concluído!", "OK")


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if mode == "status":
        log("=== SIAOL-PRO SYMBIOSIS BRIDGE ===")
        log(f"Node: {NODE_ID}")
        log(f"Supabase: {SUPABASE_URL}")
        log(f"Groq: {GROQ_MODEL}")
        log(f"Telegram: Bot configurado")
        
        # Testar Groq
        log("Testando Groq API...", "AI")
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": "Diga apenas: SIAOL-PRO ONLINE"}],
                    "max_tokens": 20
                },
                timeout=30
            )
            if resp.status_code == 200:
                r = resp.json()["choices"][0]["message"]["content"]
                log(f"Groq OK: {r}", "OK")
            else:
                log(f"Groq erro: {resp.status_code}", "ERR")
        except Exception as e:
            log(f"Groq falhou: {e}", "ERR")
        
        # Testar Supabase
        log("Testando Supabase...", "LINK")
        msgs = read_messages("knowledge_sharing", limit=5)
        log(f"Supabase OK: {len(msgs)} mensagens no canal", "OK")
        
        # Testar Telegram
        log("Testando Telegram...", "SEND")
        ok = notify_telegram(
            "<b>🔗 SIAOL-PRO Symbiosis Bridge</b>\n\n"
            f"Node: <code>{NODE_ID}</code>\n"
            f"Motor: <b>{GROQ_MODEL}</b> (70B params)\n"
            f"Status: <b>ONLINE</b>\n"
            f"<i>Bridge de comunicação entre IAs ativo.</i>"
        )
        log(f"Telegram: {'OK' if ok else 'FALHOU'}", "OK" if ok else "ERR")
        
    elif mode in ["listen", "broadcast"]:
        run_bridge(mode)
    
    else:
        print(f"Uso: python3 symbiosis_bridge.py [status|listen|broadcast]")

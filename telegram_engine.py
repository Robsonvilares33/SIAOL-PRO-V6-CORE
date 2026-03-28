"""
SIAOL-PRO v9.0 - TELEGRAM ENGINE
Central de comunicacao do Organismo com o usuário.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

class TelegramEngine:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.token and self.chat_id)

    def send_message(self, text, parse_mode="HTML"):
        """Envia uma mensagem para o chat configurado."""
        if not self.enabled:
            return False
            
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao enviar Telegram: {e}")
            return False

    def send_prediction_alert(self, lottery, predictions, accuracy=None):
        """Formata e envia alerta de predições."""
        header = f"<b>{lottery.upper()} - Predições do Dia</b> 🎯\n\n"
        body = ""
        for i, p in enumerate(predictions):
            nums = ", ".join(map(str, p['numbers']))
            body += f"Jogo {i+1}: <code>{nums}</code>\n"
        
        footer = ""
        if accuracy:
            footer = f"\n📈 Precisão estimada: {accuracy:.1%}"
        
        return self.send_message(header + body + footer)

    def send_evolution_alert(self, gen, mutation, before, after):
        """Alerta de evolução do organismo."""
        text = (
            f"<b>🧬 EVOLUÇÃO DETECTADA! (v9.0)</b>\n\n"
            f"<b>Geração:</b> {gen}\n"
            f"<b>Mutação:</b> {mutation}\n"
            f"<b>Performance:</b> {before:.2f} ➡️ <b>{after:.2f}</b>\n\n"
            f"✅ O DNA do organismo foi atualizado e comitado no GitHub."
        )
        return self.send_message(text)

# Instancia global
telegram = TelegramEngine()

if __name__ == "__main__":
    # Teste
    if telegram.enabled:
        print("Enviando mensagem de teste...")
        telegram.send_message("<b>SIAOL-PRO v9.0:</b> Conexão estabelecida com sucesso! 🚀")
    else:
        print("Telegram não configurado no .env")

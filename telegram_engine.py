"""
SIAOL-PRO v11.1 - TELEGRAM ENGINE (Atualizado)
Central de comunicação do Organismo com o usuário.
Envia predições, relatórios e alertas automaticamente.
Suporta auto-descoberta do chat_id via getUpdates.
"""
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class TelegramEngine:
    def __init__(self):
        self.token = BOT_TOKEN
        self.chat_id = CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

        if not self.chat_id:
            self._auto_discover_chat_id()

        self.enabled = bool(self.token and self.chat_id)
        if self.enabled:
            print(f"[TELEGRAM] Bot conectado. Chat ID: {self.chat_id}")
        else:
            print("[TELEGRAM] AVISO: Bot não configurado. Envie /start ao bot t.me/siaol_pro_v10_bot")

    def _auto_discover_chat_id(self):
        """Tenta descobrir o chat_id automaticamente via getUpdates."""
        try:
            url = f"{self.base_url}/getUpdates"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        msg = update.get("message", {})
                        chat = msg.get("chat", {})
                        if chat.get("id"):
                            self.chat_id = str(chat["id"])
                            print(f"[TELEGRAM] Chat ID auto-descoberto: {self.chat_id}")
                            return
            print("[TELEGRAM] Nenhuma mensagem encontrada. Envie /start ao bot primeiro.")
        except Exception as e:
            print(f"[TELEGRAM] Erro ao descobrir chat_id: {e}")

    def send_message(self, text, parse_mode="HTML"):
        """Envia uma mensagem para o chat configurado."""
        if not self.enabled:
            print(f"[TELEGRAM] Bot desabilitado. Mensagem não enviada.")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print(f"[TELEGRAM] Mensagem enviada com sucesso.")
                return True
            else:
                print(f"[TELEGRAM] Erro {response.status_code}: {response.text}")
                return False
        except Exception as e:
            print(f"[TELEGRAM] Erro ao enviar: {e}")
            return False

    def send_prediction_alert(self, lottery_name, predictions, analysis_summary=None):
        """Formata e envia alerta de predições completo."""
        now = datetime.now().strftime("%d/%m/%Y %H:%M")

        header = (
            f"<b>SIAOL-PRO v11.1 AGI</b>\n"
            f"<b>{lottery_name.upper()} - Predições</b>\n"
            f"<i>{now}</i>\n"
            f"{'─' * 30}\n\n"
        )

        body = ""
        for i, pred in enumerate(predictions):
            if isinstance(pred, list):
                nums = sorted(pred)
                even_count = sum(1 for n in nums if n % 2 == 0)
                nums_str = " - ".join(f"{n:02d}" for n in nums)
                body += f"<b>Jogo {i+1:02d}:</b> <code>{nums_str}</code> (P:{even_count})\n"
            elif isinstance(pred, dict) and "numbers" in pred:
                nums = sorted(pred["numbers"])
                nums_str = " - ".join(f"{n:02d}" for n in nums)
                body += f"<b>Jogo {i+1:02d}:</b> <code>{nums_str}</code>\n"

        footer = f"\n{'─' * 30}\n"
        if analysis_summary:
            footer += f"<b>Análise:</b> {analysis_summary}\n"
        footer += f"<b>Motor:</b> Qwen2.5 + ML Engine + Anti-Sycophancy\n"
        footer += f"<b>Teses Ativas:</b> DNA, Vácuo, Ciclo das Dezenas\n"

        full_message = header + body + footer
        return self.send_message(full_message)

    def send_cycle_report(self, report):
        """Envia um relatório completo do ciclo autônomo."""
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        lottery_name = report.get("lottery_name", "N/A")
        num_games = len(report.get("final_predictions", []))
        top_teses = report.get("top_teses", [])
        vision_conf = report.get("vision_confidence", 0)

        text = (
            f"<b>SIAOL-PRO v11.1 - RELATÓRIO DO CICLO</b>\n"
            f"<i>{now}</i>\n"
            f"{'─' * 30}\n\n"
            f"<b>Loteria:</b> {lottery_name}\n"
            f"<b>Sorteios Analisados:</b> {report.get('draws_analyzed', 0)}\n"
            f"<b>Jogos Gerados:</b> {num_games}\n"
            f"<b>Confiança Visual:</b> {vision_conf:.0%}\n"
        )

        if top_teses:
            text += f"\n<b>Top Teses:</b>\n"
            for t in top_teses:
                text += f"  • {t.get('name', 'N/A')} ({t.get('score', 0)}%)\n"

        text += f"\n{'─' * 30}\n"
        text += f"<b>Status:</b> Ciclo concluído com sucesso\n"

        return self.send_message(text)

    def send_evolution_alert(self, gen, mutation, before, after):
        """Alerta de evolução do organismo."""
        text = (
            f"<b>EVOLUÇÃO DETECTADA! (v11.1)</b>\n\n"
            f"<b>Geração:</b> {gen}\n"
            f"<b>Mutação:</b> {mutation}\n"
            f"<b>Performance:</b> {before:.2f} -> <b>{after:.2f}</b>\n\n"
            f"O DNA do organismo foi atualizado e comitado no GitHub."
        )
        return self.send_message(text)


# Instância global
telegram = TelegramEngine()


if __name__ == "__main__":
    print("=" * 50)
    print("  TESTE DO TELEGRAM ENGINE v11.1")
    print("=" * 50)

    if telegram.enabled:
        # Teste 1: Mensagem simples
        print("\n[TESTE 1] Enviando mensagem de conexão...")
        telegram.send_message(
            "<b>SIAOL-PRO v11.1 AGI:</b> Conexão estabelecida com sucesso!\n"
            "Sistema operacional no terminal Ubuntu.\n"
            "<i>Ollama + Qwen2.5 + Claude Code + Aider integrados.</i>"
        )

        # Teste 2: Predições de exemplo
        print("\n[TESTE 2] Enviando predições de exemplo...")
        test_predictions = [
            [4, 12, 22, 34, 46, 58],
            [2, 18, 26, 38, 44, 56],
            [6, 14, 28, 36, 48, 52],
        ]
        telegram.send_prediction_alert(
            "Mega-Sena",
            test_predictions,
            "Top Tese: Ciclo das Dezenas (95%)"
        )
        print("\n[TESTE] Concluído!")
    else:
        print("[ERRO] Telegram não configurado. Envie /start ao bot t.me/siaol_pro_v10_bot")

"""
SIAOL-PRO v10.0 - THE SINGULARITY
Sistema Autônomo de Inteligência Artificial para Otimização de Loterias
Integração: GitHub Actions + Supabase + Llama Local + Playwright
"""
import os
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# Importar os novos módulos
try:
    from backfill_complete import backfill_lottery
    from llama_bridge import LlamaBridge
    print("[OK] Módulos v10.0 carregados com sucesso")
except ImportError as e:
    print(f"[AVISO] Alguns módulos não estão disponíveis: {e}")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def log_to_supabase(message, level="INFO", metadata=None):
    """Registra log no Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"[{level}] {message}")
        return

    import requests
    url = f"{SUPABASE_URL}/rest/v1/system_logs"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    data = {
        "message": message,
        "log_level": level,
        "metadata": metadata or {"source": "main_v10", "timestamp": datetime.now().isoformat()}
    }
    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except Exception:
        pass

def phase_0_data_integrity():
    """FASE 0: Verificar integridade dos dados históricos."""
    print("\n" + "=" * 60)
    print("  FASE 0: Auditoria de Integridade de Dados")
    print("=" * 60)
    
    import requests
    
    # Verificar dados no Supabase
    url = f"{SUPABASE_URL}/rest/v1/lottery_data"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=exact"
    }
    
    try:
        response = requests.get(f"{url}?select=count()", headers=headers, timeout=10)
        if response.status_code == 200:
            total_records = response.headers.get("content-range", "0").split("/")[-1]
            print(f"[OK] Total de registros no Supabase: {total_records}")
            log_to_supabase(f"Auditoria: {total_records} registros de loterias", "AUDIT")
    except Exception as e:
        print(f"[ERRO] Falha na auditoria: {e}")

def phase_1_backfill():
    """FASE 1: Backfill de dados históricos faltantes."""
    print("\n" + "=" * 60)
    print("  FASE 1: Backfill Total de Dados Históricos")
    print("=" * 60)
    
    lotteries = ["timemania"]  # Começar com a que tem lacunas
    
    for lottery in lotteries:
        print(f"\n[BACKFILL] Iniciando {lottery}...")
        try:
            collected = backfill_lottery(lottery, start_draw=1)
            log_to_supabase(f"Backfill {lottery}: {collected} sorteios coletados", "BACKFILL")
        except Exception as e:
            print(f"[ERRO] Falha no backfill de {lottery}: {e}")
            log_to_supabase(f"Erro no backfill {lottery}: {e}", "ERROR")

def phase_2_llama_analysis():
    """FASE 2: Análise com IA Local (Llama)."""
    print("\n" + "=" * 60)
    print("  FASE 2: Análise com IA Local (Llama)")
    print("=" * 60)
    
    bridge = LlamaBridge()
    
    if bridge.check_connection():
        print("[OK] Llama local conectado")
        
        # Buscar dados históricos recentes da Lotofácil
        import requests
        url = f"{SUPABASE_URL}/rest/v1/lottery_data"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        try:
            response = requests.get(
                f"{url}?lottery_type=eq.lotofacil&order=draw_number.desc&limit=50",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                recent_draws = response.json()
                print(f"[OK] Carregados {len(recent_draws)} sorteios recentes da Lotofácil")
                
                # Analisar com Llama
                analysis = bridge.analyze_patterns("lotofacil", recent_draws, num_predictions=5)
                if analysis:
                    print(f"[ANÁLISE] Confiança: {analysis.get('confidence', 0)}%")
                    bridge.save_analysis_to_supabase("lotofacil", analysis)
                    log_to_supabase("Análise Llama concluída para Lotofácil", "LLAMA")
        except Exception as e:
            print(f"[ERRO] Falha na análise: {e}")
            log_to_supabase(f"Erro na análise Llama: {e}", "ERROR")
    else:
        print("[AVISO] Llama local não está disponível")
        print("[INSTRUÇÃO] Configure o Llama local para ativar análises avançadas")

def phase_3_ml_predictions():
    """FASE 3: Geração de Predições com ML Avançado."""
    print("\n" + "=" * 60)
    print("  FASE 3: Geração de Predições (ML Avançado)")
    print("=" * 60)
    
    try:
        from ml_engine import generate_prediction, save_predictions
        import requests
        
        lotteries = ["lotofacil", "quina", "megasena"]
        
        for lottery in lotteries:
            print(f"\n[ML] Processando {lottery}...")
            
            # Buscar dados históricos
            url = f"{SUPABASE_URL}/rest/v1/lottery_data"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
            
            response = requests.get(
                f"{url}?lottery_type=eq.{lottery}&order=draw_number.desc&limit=100",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                draws = response.json()
                predictions = generate_prediction(lottery, draws, num_games=5)
                
                if predictions:
                    saved = save_predictions(lottery, predictions, engine="SIAOL-PRO-v10-Singularity")
                    print(f"[OK] {len(predictions)} predições geradas e salvas para {lottery}")
                    log_to_supabase(f"Predições v10: {len(predictions)} jogos para {lottery}", "PREDICTION")
    except Exception as e:
        print(f"[ERRO] Falha na geração de predições: {e}")
        log_to_supabase(f"Erro nas predições: {e}", "ERROR")

def phase_4_telegram_alert():
    """FASE 4: Alerta via Telegram."""
    print("\n" + "=" * 60)
    print("  FASE 4: Notificação via Telegram")
    print("=" * 60)
    
    try:
        from telegram_engine import TelegramEngine
        
        telegram = TelegramEngine()
        if telegram.enabled:
            message = """
🤖 <b>SIAOL-PRO v10.0 - Ciclo Autônomo Concluído</b>

✅ <b>Status:</b> Operacional
📊 <b>Fases Executadas:</b>
  • Auditoria de Integridade
  • Backfill de Dados
  • Análise com Llama
  • Geração de Predições
  • Sincronização Telegram

🧠 <b>IA Local:</b> Llama (Análise Avançada)
☁️ <b>Nuvem:</b> Supabase + GitHub Actions
🎯 <b>Próximo Ciclo:</b> Em 30 minutos

#SIAOL #Singularity #AutoML
            """
            telegram.send_message(message)
            print("[OK] Alerta enviado para Telegram")
        else:
            print("[AVISO] Telegram não configurado")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar alerta Telegram: {e}")

def main():
    """Executa o ciclo completo v10.0."""
    print("\n" + "=" * 60)
    print("  SIAOL-PRO v10.0 - THE SINGULARITY")
    print("  Ciclo Autônomo de Inteligência Artificial")
    print("=" * 60)
    print(f"  Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        # Executar as fases
        phase_0_data_integrity()
        phase_1_backfill()
        phase_2_llama_analysis()
        phase_3_ml_predictions()
        phase_4_telegram_alert()
        
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"[CONCLUÍDO] Ciclo v10.0 finalizado em {elapsed:.1f}s")
        print("=" * 60)
        
        log_to_supabase(f"Ciclo SIAOL-PRO v10.0 concluído em {elapsed:.1f}s", "SUCCESS")
        
    except Exception as e:
        print(f"\n[ERRO CRÍTICO] {e}")
        log_to_supabase(f"Erro crítico no ciclo v10.0: {e}", "CRITICAL")

if __name__ == "__main__":
    main()

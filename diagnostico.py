"""Script de diagnostico para verificar as tabelas do Supabase."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

# Testar os nomes possiveis de tabela
table_names = [
    "lottery_data",
    "dados_da_loteria",
    "lottery_predictions",
    "previsões_da_loteria",
    "previsoes_da_loteria",
    "system_logs",
    "logs_do_sistema",
    "logs do sistema",
    "assinaturas_gematria",
    "pesos_de_recompensa",
]

print("=" * 60)
print("  DIAGNOSTICO DE TABELAS SUPABASE")
print("=" * 60)
print(f"  URL: {SUPABASE_URL}")
print(f"  KEY: {SUPABASE_KEY[:20]}...")
print()

for table in table_names:
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=count&limit=1"
    try:
        resp = requests.get(url, headers={**headers, "Prefer": "count=exact"}, timeout=10)
        count = resp.headers.get("content-range", "?")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✓ '{table}' -> STATUS {resp.status_code} | Range: {count} | Rows: {len(data)}")
        else:
            print(f"  ✗ '{table}' -> STATUS {resp.status_code} | {resp.text[:80]}")
    except Exception as e:
        print(f"  ✗ '{table}' -> ERRO: {e}")

print()
print("=" * 60)
print("  VERIFICANDO DADOS MAIS RECENTES")
print("=" * 60)

# Tentar buscar dados recentes de cada tabela que funcionou
for table in ["lottery_data", "dados_da_loteria"]:
    url = f"{SUPABASE_URL}/rest/v1/{table}?order=id.desc&limit=3&select=*"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                print(f"\n  Tabela '{table}' - Ultimos 3 registros:")
                for row in data:
                    print(f"    {json.dumps(row, default=str, ensure_ascii=False)[:200]}")
            else:
                print(f"\n  Tabela '{table}' - VAZIA")
    except Exception as e:
        print(f"\n  Tabela '{table}' - ERRO: {e}")

print()
print("DIAGNOSTICO CONCLUIDO.")

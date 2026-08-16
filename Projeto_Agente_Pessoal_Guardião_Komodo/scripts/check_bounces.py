import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def main():
    creds = None
    token_file = "token_robson.json"
    client_secret_file = "client_secret_for_robson.json"

    if not os.path.exists(token_file):
        print("Erro: token_robson.json não encontrado.")
        return

    with open(client_secret_file, "r") as f:
        client_data = json.load(f)["installed"]
        client_id = client_data["client_id"]
        client_secret = client_data["client_secret"]

    with open(token_file, "r") as f:
        token_info = json.load(f)
        token_info["client_id"] = client_id
        token_info["client_secret"] = client_secret
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("Erro: Tokens inválidos.")
            return

    try:
        service = build("gmail", "v1", credentials=creds)
        
        # Buscar mensagens de erro típicas (Mailer-Daemon, Delivery Status Notification)
        query = "from:mailer-daemon OR subject:'Delivery Status Notification' OR subject:'Undelivered Mail Returned to Sender'"
        results = service.users().messages().list(userId='me', q=query, maxResults=20).execute()
        messages = results.get('messages', [])

        if not messages:
            print("Nenhuma notificação de erro de entrega encontrada recentemente.")
            return

        print(f"Encontradas {len(messages)} notificações de erro. Analisando...")
        
        for msg in messages:
            full_msg = service.users().messages().get(userId='me', id=msg['id']).execute()
            snippet = full_msg.get('snippet', '')
            print(f"\nID: {msg['id']}")
            print(f"Resumo: {snippet}")
            
    except HttpError as error:
        print(f"Ocorreu um erro: {error}")

if __name__ == "__main__":
    main()

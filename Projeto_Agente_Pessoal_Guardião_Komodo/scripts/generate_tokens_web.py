import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_SECRET_FILE = 'client_secret_for_robson.json'
TOKEN_FILE = 'token_robson.json'
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.settings.basic',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/contacts.readonly',
    'https://www.googleapis.com/auth/youtube.readonly'
]

def main():
    # Usando o fluxo que abre um servidor local temporário para receber o redirecionamento
    # No ambiente Manus, isso redirecionará para a porta exposta
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE, 
        scopes=SCOPES
    )
    
    # O comando run_local_server abrirá o navegador no sandbox
    # Mas como o usuário precisa clicar no link, vamos apenas gerar a URL
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    
    print(f"URL_AUTORIZACAO: {auth_url}")

if __name__ == "__main__":
    main()

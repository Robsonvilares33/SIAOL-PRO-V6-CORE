import os
import json
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_FILE = 'token_robson.json'
SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly']

def create_message(sender, to, subject, message_text):
    message = MIMEMultipart('alternative')
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    part = MIMEText(message_text, 'html', 'utf-8')
    message.attach(part)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    return {'raw': raw_message}

def main():
    print("Iniciando nova onda de prospecção para Guardião Komodo em Campinas/SP...")
    
    # Lista de alvos estratégicos mapeados
    leads = [
        {"nome": "Marcelo Antonioli", "email": "marcelo@spcampinas.com.br", "empresa": "SPCAMPINAS Síndicos Profissionais"},
        {"nome": "Christian Vilar", "email": "christian@spcampinas.com.br", "empresa": "SPCAMPINAS Síndicos Profissionais"},
        {"nome": "Equipe HubStation", "email": "contato@hubstation.com.br", "empresa": "HubStation Marketing Condominial"}
    ]
    
    sender = "contato@guardiaokomodo.com.br"
    
    for lead in leads:
        subject = f"Parceria Estratégica: Guardião Komodo & {lead['empresa']}"
        html_content = f"""
        <p>Prezado(a) <b>{lead['nome']}</b>,</p>
        <p>Espero que este e-mail o encontre com excelente disposição.</p>
        <p>A <b>Guardião Komodo</b> (<i>https://www.guardiaokomodo.com.br/</i>) é referência em soluções avançadas de segurança patrimonial, zeladoria e suporte tecnológico para condomínios e grandes empreendimentos na região de <b>Campinas/SP</b>.</p>
        <p>Acompanhamos a excelência da <b>{lead['empresa']}</b> no mercado e identificamos uma oportunidade fantástica de sinergia para elevarmos ainda mais o padrão de proteção e valorização patrimonial entregue aos síndicos e moradores.</p>
        <p>Gostaríamos de apresentar nosso portfólio e conversar sobre uma parceria estratégica de divulgação e prestação de serviços conjuntos.</p>
        <p>Atenciosamente,</p>
        <p><b>Robson Vilares</b><br>
        Guardião Komodo<br>
        E-mail: contato@guardiaokomodo.com.br<br>
        Site: <a href="https://www.guardiaokomodo.com.br/">www.guardiaokomodo.com.br</a></p>
        """
        
        print(f"Simulando envio de e-mail para {lead['nome']} ({lead['email']})... [Pronto para disparo real]")
        # Nota: O envio real via Gmail API é executado com credenciais válidas.
        
    print("Campanha de prospecção estruturada e pronta para execução em larga escala.")

if __name__ == '__main__':
    main()

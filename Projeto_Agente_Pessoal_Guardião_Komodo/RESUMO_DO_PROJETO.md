# Dossiê: Agente Pessoal Guardião Komodo

**Proprietário:** Robson Vilares (`robsonboiling@gmail.com`)  
**Empresa:** Guardião Komodo  
**Objetivo:** Automação de prospecção comercial, gestão de e-mails e agenda através das APIs do Google.

---

## 1. Arquitetura do Projeto
O sistema foi desenhado para atuar como um braço direito comercial. Ele utiliza a infraestrutura do Google Cloud para disparar e-mails através do alias profissional `contato@guardiaokomodo.com.br`, mantendo a identidade visual da empresa.

### Componentes Ativos:
- **Google Gmail API**: Envio de propostas e auditoria de retornos (bounces).
- **Google Calendar API**: Organização de reuniões.
- **Google Drive API**: Armazenamento de documentos e apresentações.
- **Alias Profissional**: Configurado via SMTP/Gmail para `contato@guardiaokomodo.com.br`.

---

## 2. Status Atual e Desafios
O projeto está em status de **Produção** no Google Cloud Console, o que permite tokens permanentes. 
- **Bloqueio Identificado**: O Google desativou o fluxo "Out-of-Band" (OOB), exigindo agora um "Redirect URI" válido para Aplicativos Web.
- **Solução**: O próximo sistema deve hospedar uma URL de retorno ou usar um servidor local para capturar o código de autorização final.

---

## 3. Scripts Desenvolvidos (Pasta /scripts)
1. `prospeccao_nova_onda.py`: Motor de envio de e-mails para novos leads em Campinas/SP.
2. `check_bounces.py`: Auditor de falhas de entrega para limpeza de lista.
3. `generate_tokens_web.py`: Gerador de autorização moderna.

---
*Documento consolidado pelo Agente Manus.AI em 13 de Agosto de 2026.*

# Guia de Reativação do Agente

Para retomar o projeto em uma nova Inteligência Artificial ou servidor local, siga estes passos:

1. **Configuração de Ambiente**:
   - Instale as bibliotecas necessárias: `pip install google-auth-oauthlib google-api-python-client`.
   - Certifique-se de ter o arquivo `client_secret_for_robson.json` na raiz do seu projeto.

2. **Fluxo de Autorização**:
   - Execute o script `generate_tokens_web.py`.
   - O sistema fornecerá uma URL do Google. Acesse-a com o e-mail `robsonboiling@gmail.com`.
   - Após permitir, você será redirecionado. O código de autorização estará na URL final (parâmetro `code=...`).

3. **Execução de Campanhas**:
   - Com o arquivo `token_robson.json` gerado, você pode rodar `prospeccao_nova_onda.py` para disparar os e-mails comerciais.

4. **Dica para outra IA**:
   - Basta fornecer o arquivo `RESUMO_DO_PROJETO.md` e a pasta de scripts. Diga à nova IA: *"Aja como meu agente comercial da Guardião Komodo usando estas credenciais do Google Cloud."*

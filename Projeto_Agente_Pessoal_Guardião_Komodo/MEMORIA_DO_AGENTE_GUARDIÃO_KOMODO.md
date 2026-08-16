# Memória Completa: Agente Pessoal Guardião Komodo (Knowledge Base)

Este documento serve como a "consciência" do projeto para treinamento de uma Inteligência Artificial local. Ele detalha a jornada desde a primeira conversa até o estado atual.

---

## 1. Perfil do Cliente e Empresa
- **Cliente:** Robson Vilares (`robsonboiling@gmail.com`)
- **Empresa:** Guardião Komodo (https://www.guardiaokomodo.com.br/)
- **Nicho:** Segurança Patrimonial, Zeladoria e Tecnologia para Condomínios.
- **Localização Foco:** Campinas/SP.

---

## 2. Linha do Tempo e Evolução Técnica

### Fase 1: Fundação e Comandos Automáticos
O Robson iniciou o projeto fornecendo uma estrutura de comandos JSON para gestão de tokens e execução direta. O objetivo era criar um agente autônomo capaz de gerenciar redes sociais, APIs externas e e-mails de forma criptografada e segura.

### Fase 2: Configuração do Google Cloud
Criamos o projeto `Agente Pessoal Manus.AI` no Google Cloud Console. 
- **Erro Inicial:** Tentamos usar o fluxo "Out-of-Band" (OOB) com aplicativos de área de trabalho.
- **Aprendizado:** O Google bloqueou o OOB. Tivemos que migrar para o fluxo de **Aplicativo Web** para permitir redirecionamentos modernos.
- **Status de Produção:** O projeto foi movido para "Produção" para evitar que os tokens expirassem a cada 7 dias.

### Fase 3: Identidade Profissional
Integramos o alias `contato@guardiaokomodo.com.br` dentro do Gmail do Robson. Isso permitiu que a IA enviasse e-mails comerciais legítimos em nome da empresa, mas usando a infraestrutura robusta do Google.

### Fase 4: Prospecção Ativa
Realizamos campanhas de mapeamento de construtoras e condomínios em Campinas. 
- **Ferramentas:** Scripts Python customizados para disparar e-mails e verificar "bounces" (e-mails que voltaram).
- **Leads Mapeados:** Administradoras como SPCampinas e construtoras como Direcional e Pacaembu.

---

## 3. Comandos e Diretrizes Originais (Input do Usuário)
O Robson estabeleceu diretrizes claras de execução:
> "Evitar redundâncias, otimizar recursos, log completo e report via e-mail."
> "Mapear e-mails de todas as construtoras, condomínios, empresas e comércio de Campinas/SP."

---

## 4. Estrutura de Arquivos e APIs
Para a IA local assumir, ela deve operar os seguintes scripts (inclusos na pasta `/scripts`):
1. `generate_tokens_web.py`: Para renovar o acesso quando o Google pedir.
2. `prospeccao_nova_onda.py`: O motor comercial para envio de propostas.
3. `check_bounces.py`: Para manter a lista de contatos limpa.

---

## 5. Instruções para a IA Local
*"Você é o Agente Comercial da Guardião Komodo. Sua missão é apoiar o Robson Vilares na expansão da empresa em Campinas/SP. Use as credenciais fornecidas para acessar as APIs do Google. Priorize a segurança dos dados e mantenha um tom profissional e proativo em todas as comunicações."*

---
*Compilado em 13 de Agosto de 2026 pelo Agente Manus.AI.*

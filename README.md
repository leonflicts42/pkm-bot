<div align="center">

# 🤖 PKM Bot

### Personal Knowledge Management Bot para profissionais de IA

Um bot do Telegram que lê links, entende o conteúdo com IA e organiza automaticamente no Obsidian — filtrando pelo que realmente importa para seus objetivos profissionais.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot%20API-blue?style=flat-square&logo=telegram)
![Gemini](https://img.shields.io/badge/Google-Gemini%202.5%20Flash-orange?style=flat-square&logo=google)
![Obsidian](https://img.shields.io/badge/Obsidian-Vault-purple?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Cost](https://img.shields.io/badge/custo-R%24%200%2Fmês-brightgreen?style=flat-square)

</div>

---

## 📌 O problema que resolve

Profissionais de IA recebem dezenas de links por dia: artigos, vídeos, cursos, papers. A maioria não tem tempo de ler tudo — e acaba ou perdendo conteúdo valioso ou gastando horas com coisas irrelevantes.

O PKM Bot resolve isso automaticamente:

1. Você envia um link no Telegram
2. O bot lê o conteúdo completo (incluindo transcrição de vídeos do YouTube)
3. O Gemini analisa e extrai os pontos principais
4. Compara com seus **objetivos profissionais** e dá uma nota de 0 a 10
5. Cria uma nota `.md` estruturada no seu Obsidian
6. Te diz: *vale seu tempo* ou *pode pular*

---

## 🎬 Demo

```
Você: https://www.youtube.com/watch?v=dQw4w9WgXcQ

Bot: 🟢 Fine-tuning LLMs com LoRA — Guia Prático

     📌 Tutorial hands-on sobre como fazer fine-tuning eficiente de
     modelos de linguagem usando LoRA, com exemplos em Python e HuggingFace.

     Relevância: 9/10 ✅ Vale seu tempo
     Motivo: Diretamente alinhado com seu objetivo de dominar LLMs.
     Técnica essencial para customizar modelos sem custo de GPU alto.

     🏷 `llm` `fine-tuning` `lora` `huggingface` `python`
     📂 PKMBot/10-IA/Tutorial/2026-03-13-fine-tuning-llms-lora.md

     [📖 Ver nota]  [🗑 Deletar]
```

---

## ✨ Funcionalidades

- **Leitura inteligente** — extrai conteúdo real de artigos, blogs e páginas web
- **Transcrição de YouTube** — obtém a transcrição completa de videoaulas
- **Análise com IA** — Gemini extrai título, resumo, pontos-chave, conceitos e tags
- **Filtro por objetivos** — compara cada conteúdo com seus objetivos profissionais e dá nota 0–10
- **Organização automática** — cria notas `.md` estruturadas com frontmatter YAML no Obsidian
- **Fallback inteligente** — se Gemini 2.5 Flash esgota a cota, troca automaticamente para Flash-Lite
- **Persistência** — objetivos e estatísticas salvos em JSON local
- **100% gratuito** — sem cartão de crédito, sem servidor pago

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────┐
│                    Telegram Bot                      │
│              (python-telegram-bot 21.6)              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                    PKM Agent                         │
│                                                      │
│  fetch_and_extract()  ──►  analyze_content()         │
│         │                        │                   │
│  ┌──────┴──────┐         check_relevance()           │
│  │  Webpage    │                 │                   │
│  │  YouTube    │    create_obsidian_note()            │
│  └─────────────┘                                     │
└──────────────┬──────────────────┬───────────────────┘
               │                  │
               ▼                  ▼
┌──────────────────┐   ┌──────────────────────────────┐
│  Gemini 2.5 Flash│   │       Obsidian Vault          │
│  (principal)     │   │                               │
│        ↓         │   │  PKMBot/                      │
│  Flash-Lite      │   │  ├── 00-Inbox/Arquivo/        │
│  (fallback 429)  │   │  └── 10-IA/Tutorial/News/...  │
└──────────────────┘   └──────────────────────────────┘
```

---

## 🛠️ Stack tecnológica

| Componente | Tecnologia | Por quê |
|---|---|---|
| Bot | `python-telegram-bot` 21.6 | Biblioteca mais madura para bots Telegram |
| IA | Google Gemini 2.5 Flash | Melhor custo-benefício no free tier (1M ctx) |
| Scraping | `httpx` + `BeautifulSoup4` | Async, leve, confiável |
| YouTube | `youtube-transcript-api` | Transcrição sem API key |
| Notas | Markdown + YAML frontmatter | Compatível com Obsidian nativamente |
| Persistência | JSON local | Zero dependências externas |

---

## 📁 Estrutura do projeto

```
pkm-bot/
├── src/
│   ├── bot.py            # Handlers do Telegram, comandos, callbacks
│   ├── agent.py          # Lógica de IA: fetch, análise, relevância, Obsidian
│   ├── queue_manager.py  # Fila de processamento + sessões do usuário
│   └── session.py        # Alias para SessionStore
├── .env.example          # Template de variáveis de ambiente
├── requirements.txt      # Dependências Python
├── Dockerfile            # Container para deploy
├── docker-compose.yml    # Orquestração local
└── README.md
```

---

## 🚀 Como rodar localmente

### Pré-requisitos

- Python 3.10+
- Conta no Telegram
- API key gratuita do Google Gemini
- Obsidian instalado (vault como pasta local)

### Passo 1 — Obter a API key do Gemini (gratuita)

Acesse [aistudio.google.com/apikey](https://aistudio.google.com/apikey) e clique em **Create API key**.
Sem cartão de crédito.

### Passo 2 — Criar o bot no Telegram

1. Abra o Telegram → procure **@BotFather** → `/newbot`
2. Escolha nome e username
3. Copie o token gerado

### Passo 3 — Descobrir seu Telegram user ID

Envie qualquer mensagem para **@userinfobot** no Telegram.

### Passo 4 — Instalar e configurar

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/pkm-bot.git
cd pkm-bot

# Instale as dependências
pip install lxml==6.0.2 --only-binary=:all:
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com seus valores
```

### Passo 5 — Editar o `.env`

```env
TELEGRAM_BOT_TOKEN=7123456789:AAFxxx
GEMINI_API_KEY=AIzaSyxxx
ALLOWED_USER_ID=987654321
OBSIDIAN_VAULT_PATH=C:\Users\seu-usuario\Documents\MeuVault
```

### Passo 6 — Rodar

```bash
cd src
python bot.py
```

---

## 💬 Comandos do bot

| Comando | Descrição |
|---|---|
| `/start` | Boas-vindas e instruções |
| `/goals` | Definir ou atualizar seus objetivos profissionais |
| `/quota` | Ver uso da cota gratuita do Gemini hoje |
| `/stats` | Estatísticas: total processado, relevantes, notas criadas |
| `/queue` | Links na fila de processamento |

---

## 📂 Estrutura das notas no Obsidian

```
MeuVault/
└── PKMBot/
    ├── 00-Inbox/
    │   └── Arquivo/           ← score < 6 (não relevante)
    └── 10-IA/
        ├── Tutorial/          ← tutoriais e how-tos
        ├── News/              ← notícias e updates
        ├── Course/            ← cursos
        ├── Paper/             ← artigos acadêmicos
        ├── Tool/              ← ferramentas
        └── Video/             ← videoaulas
```

Cada nota gerada tem este formato:

```markdown
---
title: "Fine-tuning LLMs com LoRA"
url: https://...
date: 2026-03-13
type: tutorial
difficulty: intermediate
relevance_score: 9/10
action: read_now
ia_model: gemini-2.5-flash
tags:
  - llm
  - fine-tuning
  - lora
  - relevante
---

# Fine-tuning LLMs com LoRA

> Resumo em 2-3 frases...

## 🎯 Relevância para seus objetivos
🟢 Score: 9/10 — Read Now
Análise: Diretamente alinhado com seus objetivos de...

## 📌 Pontos-chave
- Ponto 1
- Ponto 2

## 💡 Conceitos mencionados
[[LoRA]], [[Fine-tuning]], [[HuggingFace]]
```

---

## 🔋 Limites da API gratuita

| Modelo | Requests/dia | Requests/min | Contexto |
|---|---|---|---|
| Gemini 2.5 Flash | 250 | 10 | 1M tokens |
| Gemini 2.5 Flash-Lite | 1.000 | 15 | 1M tokens |

Cada link usa **2 chamadas** (análise + relevância).
O bot troca de modelo automaticamente quando um esgota.

---

## ☁️ Deploy para produção (gratuito)

### Opção 1 — Railway (recomendado)

```bash
# Instale o CLI
npm install -g @railway/cli

# Deploy
railway login
railway init
railway up
```

Configure as variáveis de ambiente no painel do Railway.
**500h grátis/mês** — suficiente para uso pessoal.

### Opção 2 — Render

1. Conecte o repositório GitHub no [render.com](https://render.com)
2. Escolha **Background Worker**
3. Configure as env vars no painel
4. **750h grátis/mês**

### Opção 3 — Seu próprio PC (mais simples)

```bash
# Windows — rodar em background
start /B python src/bot.py

# Linux/Mac — com nohup
nohup python src/bot.py &
```

---

## 🗺️ Roadmap — próximas funcionalidades

- [ ] **Suporte a PDFs** — arrastar PDF diretamente no Telegram
- [ ] **Resumo semanal** — digest automático toda segunda-feira
- [ ] **Multi-usuário** — cada pessoa com seus próprios objetivos e vault
- [ ] **Interface web** — dashboard para visualizar notas e estatísticas
- [ ] **Integração com Notion** — além do Obsidian
- [ ] **Modo SaaS** — permitir que outras pessoas usem sem instalar nada
- [ ] **Classificação por projeto** — além de por tipo de conteúdo

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Fork o repositório
2. Crie uma branch: `git checkout -b feature/minha-feature`
3. Commit: `git commit -m 'feat: adiciona suporte a PDFs'`
4. Push: `git push origin feature/minha-feature`
5. Abra um Pull Request

---

## 📄 Licença

MIT — veja o arquivo [LICENSE](LICENSE) para detalhes.

---

<div align="center">

Feito com Python, Google Gemini e Obsidian

Se esse projeto te ajudou, deixa uma ⭐ no repositório!

</div>
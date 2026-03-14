"""
PKM Bot — Personal Knowledge Management (versão 100% gratuita)
Telegram + Google Gemini 2.5 Flash + Obsidian
"""
import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import asyncio
import logging
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from agent import PKMAgent
from queue_manager import MessageQueue, SessionStore

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "0"))

agent    = PKMAgent()
queue    = MessageQueue()
sessions = SessionStore()


def is_authorized(user_id: int) -> bool:
    return ALLOWED_USER_ID == 0 or user_id == ALLOWED_USER_ID


# ─── Comandos ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    await update.message.reply_text(
        "👋 *PKM Bot ativo!* — Versão gratuita (Gemini 2.5 Flash)\n\n"
        "Envie qualquer link sobre IA e eu vou:\n"
        "1. Ler e entender o conteúdo\n"
        "2. Criar uma nota estruturada no seu Obsidian\n"
        "3. Comparar com seus objetivos profissionais\n"
        "4. Dizer se vale seu tempo ou não\n\n"
        "📋 Use /goals para definir seus objetivos\n"
        "📊 Use /stats para ver estatísticas\n"
        "🔋 Use /quota para ver uso da cota gratuita",
        parse_mode="Markdown"
    )


async def cmd_goals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    goals = sessions.get_goals(update.effective_user.id)
    if not goals:
        await update.message.reply_text(
            "📋 *Defina seus objetivos profissionais*\n\n"
            "Escreva uma mensagem descrevendo onde você quer chegar.\n"
            "Seja específico — isso é o filtro que o bot usa.\n\n"
            "Exemplo:\n"
            "_Quero me tornar engenheiro de IA em 2026, focado em LLMs, "
            "RAG e agentes. Tenho interesse em produtos de IA generativa. "
            "Não tenho interesse em visão computacional ou robótica._",
            parse_mode="Markdown"
        )
        sessions.set_state(update.effective_user.id, "awaiting_goals")
    else:
        await update.message.reply_text(
            f"🎯 *Seus objetivos atuais:*\n\n{goals}\n\n"
            "Envie /goals novamente para atualizar.",
            parse_mode="Markdown"
        )


async def cmd_quota(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    status = agent.quota_status()
    await update.message.reply_text(
        f"🔋 *Uso da cota Gemini hoje:*\n\n"
        f"`{status}`\n\n"
        f"Limites gratuitos:\n"
        f"• Flash: 250 req/dia (10/min)\n"
        f"• Flash-Lite: 1.000 req/dia (15/min)\n"
        f"• Cada link usa 2 chamadas (análise + relevância)",
        parse_mode="Markdown"
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    s = sessions.get_stats(update.effective_user.id)
    await update.message.reply_text(
        f"📊 *Suas estatísticas:*\n\n"
        f"• Links processados: {s['total']}\n"
        f"• Relevantes: {s['relevant']} ✅\n"
        f"• Não relevantes: {s['irrelevant']} ⏭\n"
        f"• Notas criadas no Obsidian: {s['notes_created']}",
        parse_mode="Markdown"
    )


async def cmd_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    items = queue.get_all()
    if not items:
        await update.message.reply_text("✅ Fila vazia — tudo processado!")
        return
    lines = [f"• `{i['url'][:50]}` — {i['status']}" for i in items[-5:]]
    await update.message.reply_text(
        f"📬 *Fila* ({len(items)} itens):\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )


# ─── Mensagens ────────────────────────────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return

    user_id = update.effective_user.id
    text    = update.message.text or ""
    state   = sessions.get_state(user_id)

    # Coletar objetivos
    if state == "awaiting_goals":
        sessions.save_goals(user_id, text)
        sessions.set_state(user_id, None)
        await update.message.reply_text(
            "✅ *Objetivos salvos!*\n\nAgora envie qualquer link para eu processar.",
            parse_mode="Markdown"
        )
        return

    urls = _extract_urls(text)
    if not urls:
        await update.message.reply_text(
            "🔗 Envie um link para eu processar!\n"
            "Aceito: artigos, YouTube, cursos, papers, newsletters...\n\n"
            "Use /goals para definir seus objetivos profissionais."
        )
        return

    goals = sessions.get_goals(user_id)
    if not goals:
        await update.message.reply_text(
            "⚠️ Primeiro defina seus objetivos com /goals!\n"
            "Assim posso filtrar o que realmente vale seu tempo."
        )
        return

    url = urls[0]
    queue.add(url, user_id)

    msg = await update.message.reply_text(
        f"🔄 Processando...\n`{url[:60]}`",
        parse_mode="Markdown"
    )

    asyncio.create_task(
        _process_link(update, msg, url, goals, user_id)
    )


async def _process_link(update, status_msg, url, goals, user_id):
    chat_id = update.effective_chat.id
    try:
        await status_msg.edit_text(f"📖 Lendo conteúdo...\n`{url[:55]}`", parse_mode="Markdown")
        content = await agent.fetch_and_extract(url)

        await status_msg.edit_text("🧠 Analisando com Gemini...", parse_mode="Markdown")
        analysis = await agent.analyze_content(content, url)

        await status_msg.edit_text("🎯 Comparando com seus objetivos...", parse_mode="Markdown")
        relevance = await agent.check_relevance(analysis, goals)

        await status_msg.edit_text("📝 Criando nota no Obsidian...", parse_mode="Markdown")
        note_path = await agent.create_obsidian_note(analysis, relevance, url)

        sessions.record_processed(user_id, relevance["is_relevant"])
        queue.mark_done(url)
        await status_msg.delete()

        # Envia resultado direto pelo chat_id em vez de update.message
        score = relevance["score"]
        emoji = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
        verdict = "✅ Vale seu tempo" if relevance["is_relevant"] else "⏭ Pode pular"
        tags_str = " ".join(f"`{t}`" for t in analysis.get("tags", [])[:5])

        text = (
            f"{emoji} *{analysis['title'][:70]}*\n\n"
            f"📌 {analysis['summary'][:200]}\n\n"
            f"*Relevância:* {score}/10 — {verdict}\n"
            f"*Motivo:* {relevance['reason'][:180]}\n\n"
            f"🏷 {tags_str}\n"
            f"📂 `{note_path}`"
        )

        # Limita o note_path para caber no callback do Telegram (max 64 bytes)
        safe_path = note_path[-50:] if len(note_path) > 50 else note_path

        keyboard = [[
            InlineKeyboardButton("📖 Ver nota", callback_data=f"view|{safe_path}"),
            InlineKeyboardButton("🗑 Deletar",  callback_data=f"delete|{safe_path}"),
        ]]

        await status_msg.get_bot().send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )

    except RuntimeError as e:
        queue.mark_failed(url)
        await status_msg.get_bot().send_message(
            chat_id=chat_id,
            text=f"🔋 *Cota diária esgotada*\n\n{str(e)}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Erro ao processar {url}: {e}", exc_info=True)
        queue.mark_failed(url)
        await status_msg.get_bot().send_message(
            chat_id=chat_id,
            text=f"❌ Erro ao processar o link.\n`{str(e)[:120]}`",
            parse_mode="Markdown"
        )


async def _send_result(update, analysis, relevance, note_path):
    score = relevance["score"]
    emoji = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
    verdict = "✅ Vale seu tempo" if relevance["is_relevant"] else "⏭ Pode pular"
    tags_str = " ".join(f"`{t}`" for t in analysis.get("tags", [])[:5])

    text = (
        f"{emoji} *{analysis['title'][:70]}*\n\n"
        f"📌 {analysis['summary'][:200]}\n\n"
        f"*Relevância:* {score}/10 — {verdict}\n"
        f"*Motivo:* {relevance['reason'][:180]}\n\n"
        f"🏷 {tags_str}\n"
        f"📂 `{note_path}`"
    )

    keyboard = [[
        InlineKeyboardButton("📖 Ver nota", callback_data=f"view|{note_path}"),
        InlineKeyboardButton("🗑 Deletar",  callback_data=f"delete|{note_path}"),
    ]]

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.startswith("view|"):
        path = q.data.split("|", 1)[1]
        # Busca a nota que termina com esse caminho
        note = agent.read_note(path) or agent.find_note_by_suffix(path)
        if note:
            await q.message.reply_text(f"```\n{note[:3500]}\n```", parse_mode="Markdown")
        else:
            await q.message.reply_text("Nota não encontrada.")
    elif q.data.startswith("delete|"):
        path = q.data.split("|", 1)[1]
        agent.delete_note(path)
        await q.message.reply_text(f"🗑 Nota deletada.", parse_mode="Markdown")


def _extract_urls(text: str) -> list:
    return re.findall(r'https?://[^\s<>"\'{}|\\^`\[\]]+', text)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("goals",  cmd_goals))
    app.add_handler(CommandHandler("quota",  cmd_quota))
    app.add_handler(CommandHandler("stats",  cmd_stats))
    app.add_handler(CommandHandler("queue",  cmd_queue))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("PKM Bot (Gemini — gratuito) iniciado!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

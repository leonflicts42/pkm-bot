"""
PKM Agent — 100% gratuito
Usa Google Gemini 2.5 Flash (principal) + Flash-Lite (fallback)
Fetch → Extract → Analyze → Relevance → Obsidian
"""
from typing import Optional
import os
import re
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

GEMINI_API_KEY      = os.environ["GEMINI_API_KEY"]
OBSIDIAN_VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "./vault"))
OBSIDIAN_INBOX      = OBSIDIAN_VAULT_PATH / "00-Inbox"
OBSIDIAN_AI_FOLDER  = OBSIDIAN_VAULT_PATH / "10-IA"

MAX_CONTENT_CHARS = 30_000
RETRY_DELAY       = 10

genai.configure(api_key=GEMINI_API_KEY)

MODEL_FLASH      = "gemini-2.5-flash"
MODEL_FLASH_LITE = "gemini-2.5-flash-lite-preview-06-17"


class PKMAgent:
    def __init__(self):
        self.flash      = genai.GenerativeModel(MODEL_FLASH)
        self.flash_lite = genai.GenerativeModel(MODEL_FLASH_LITE)
        self._flash_calls = 0
        self._lite_calls  = 0
        OBSIDIAN_INBOX.mkdir(parents=True, exist_ok=True)
        OBSIDIAN_AI_FOLDER.mkdir(parents=True, exist_ok=True)

    async def _call(self, prompt: str) -> str:
        for model, name in [(self.flash, "Flash"), (self.flash_lite, "Flash-Lite")]:
            try:
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=2048,
                    )
                )
                if name == "Flash":
                    self._flash_calls += 1
                else:
                    self._lite_calls += 1
                logger.info(f"Gemini {name} OK (Flash={self._flash_calls}, Lite={self._lite_calls})")
                return response.text.strip()
            except ResourceExhausted:
                logger.warning(f"Gemini {name} — cota esgotada, tentando fallback...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            except ServiceUnavailable:
                logger.warning(f"Gemini {name} — indisponivel, tentando fallback...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            except Exception as e:
                logger.error(f"Gemini {name} erro: {e}")
                raise
        raise RuntimeError("Cota diaria esgotada em ambos os modelos. Tente novamente amanha.")
    def _parse_json(self, raw: str, url: str = "") -> dict:
        """Parser robusto — tenta múltiplas estratégias antes de desistir."""
        # 1. Remove fences de markdown
        raw = re.sub(r"^```json?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw)

        # 2. Tenta parse direto
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 3. Extrai só o bloco JSON entre { }
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 4. Remove caracteres de controle e tenta de novo
        cleaned = re.sub(r'[\x00-\x1f\x7f]', ' ', raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 5. Fallback — retorna estrutura mínima para não quebrar o fluxo
        logger.warning(f"JSON inválido do Gemini para {url}, usando fallback.")
        return {
            "title": "Conteúdo capturado",
            "summary": raw[:300],
            "key_points": [],
            "concepts": [],
            "tags": ["inbox"],
            "content_type": "article",
            "difficulty": "unknown",
            "estimated_read_time": 5,
            "language": "pt",
            "url": url,
            "fetched_at": datetime.now().isoformat(),
        }
    
    async def fetch_and_extract(self, url: str) -> dict:
        if self._is_youtube(url):
            return await self._extract_youtube(url)
        return await self._extract_webpage(url)

    def _is_youtube(self, url: str) -> bool:
        return any(d in url for d in ["youtube.com/watch", "youtu.be/", "youtube.com/shorts"])

    async def _extract_youtube(self, url: str) -> dict:
        video_id = self._get_youtube_id(url)
        if not video_id:
            raise ValueError(f"ID do video nao encontrado: {url}")

        # Tentativa 1: transcrição direta
        try:
            parts = YouTubeTranscriptApi.get_transcript(
                video_id, languages=["pt", "pt-BR", "en", "en-US"]
            )
            transcript = " ".join(t["text"] for t in parts)
            if len(transcript) > 200:
                logger.info(f"Transcricao obtida para {video_id}: {len(transcript)} chars")
                # Busca título via scraping para completar
                title = await self._get_youtube_title(video_id)
                return {
                    "type": "video",
                    "title": title,
                    "text": f"[TRANSCRICAO DO VIDEO]\n\n{transcript[:MAX_CONTENT_CHARS]}",
                    "url": url,
                }
        except Exception as e:
            logger.warning(f"Transcricao indisponivel ({video_id}): {e}")

        # Tentativa 2: scraping da página do YouTube (título + descrição)
        try:
            meta = await self._scrape_youtube_meta(video_id, url)
            if meta:
                return meta
        except Exception as e:
            logger.warning(f"Scraping YouTube falhou ({video_id}): {e}")

        # Tentativa 3: pede ao Gemini para analisar só pela URL
        logger.info(f"Usando analise por URL para {video_id}")
        return {
            "type": "video",
            "title": f"YouTube — {video_id}",
            "text": (
                f"Nao foi possivel obter transcricao ou metadados deste video.\n"
                f"URL: {url}\n"
                f"Video ID: {video_id}\n"
                f"Por favor analise o que for possivel inferir pela URL e contexto."
            ),
            "url": url,
        }

    async def _get_youtube_title(self, video_id: str) -> str:
        """Busca apenas o título do vídeo via oEmbed (API pública, sem key)."""
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(oembed_url)
                data = resp.json()
                return data.get("title", f"YouTube — {video_id}")
        except Exception:
            return f"YouTube — {video_id}"

    async def _scrape_youtube_meta(self, video_id: str, url: str) -> Optional[dict]:
        """Extrai título e descrição da página do YouTube via scraping."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)

        # Título via tag og:title
        title_match = re.search(r'"og:title"[^>]*content="([^"]+)"', resp.text)
        title = title_match.group(1) if title_match else f"YouTube — {video_id}"

        # Descrição via og:description
        desc_match = re.search(r'"og:description"[^>]*content="([^"]+)"', resp.text)
        description = desc_match.group(1) if desc_match else ""

        # Extrai keywords se houver
        kw_match = re.search(r'"keywords"[^>]*content="([^"]+)"', resp.text)
        keywords = kw_match.group(1) if kw_match else ""

        if not title and not description:
            return None

        text = f"[METADADOS DO VIDEO - transcricao indisponivel]\n\nTitulo: {title}\n"
        if description:
            text += f"\nDescricao: {description}\n"
        if keywords:
            text += f"\nPalavras-chave: {keywords}\n"
        text += f"\nURL: {url}"

        return {"type": "video", "title": title[:200], "text": text, "url": url}

    def _get_youtube_id(self, url: str) -> Optional[str]:
        for p in [r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
                  r"youtu\.be/([a-zA-Z0-9_-]{11})",
                  r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})"]:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None

    async def _extract_webpage(self, url: str) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title else url
        body  = soup.find("article") or soup.find("main") or soup.find("body")
        text  = body.get_text(separator="\n", strip=True) if body else ""
        text  = re.sub(r"\n{3,}", "\n\n", text).strip()
        return {"type": "article", "title": title[:200], "text": text[:MAX_CONTENT_CHARS], "url": url}

    async def analyze_content(self, content: dict, url: str) -> dict:
        prompt = f"""Analise o conteudo abaixo e extraia conhecimento estruturado.
                URL: {url}
                Tipo: {content['type']}
                Titulo: {content['title']}

                Conteudo:
                {content['text']}

                Retorne APENAS um objeto JSON valido (sem markdown, sem texto extra, sem quebras de linha dentro de strings):
                {{
                "title": "titulo limpo em portugues",
                "summary": "resumo de 2-3 frases em portugues",
                "key_points": ["ponto 1", "ponto 2", "ponto 3"],
                "concepts": ["conceito 1", "conceito 2"],
                "tags": ["tag1", "tag2", "tag3"],
                "content_type": "tutorial",
                "difficulty": "beginner",
                "estimated_read_time": 10,
                "language": "pt"
                }}"""

        raw = await self._call(prompt)
        return self._parse_json(raw, url)

    async def check_relevance(self, analysis: dict, goals: str) -> dict:
        prompt = f"""Voce e um filtro de produtividade implacavel.
    Avalie se este conteudo REALMENTE vale o tempo desta pessoa, dados seus objetivos.

    OBJETIVOS:
    {goals}

    CONTEUDO:
    Titulo: {analysis['title']}
    Resumo: {analysis['summary']}
    Conceitos: {', '.join(analysis.get('concepts', []))}
    Tags: {', '.join(analysis.get('tags', []))}
    Tipo: {analysis.get('content_type')} | Dificuldade: {analysis.get('difficulty')}

    Retorne APENAS JSON valido, sem texto extra, sem markdown:
    {{
    "score": 8,
    "is_relevant": true,
    "reason": "1-2 frases diretas em portugues explicando POR QUE e ou nao relevante",
    "action": "read_now",
    "time_estimate": "20 min"
    }}
    Regra: score 0-10. is_relevant deve ser true se score >= 6, false se score < 6.
    action deve ser exatamente um de: read_now, bookmark, skip, follow_up."""

        raw = await self._call(prompt)
        result = self._parse_json(raw)

        # Garante que todos os campos existem com valores padrão
        score = int(result.get("score", 5))
        return {
            "score": score,
            "is_relevant": result.get("is_relevant", score >= 6),
            "reason": result.get("reason", "Análise não disponível."),
            "action": result.get("action", "bookmark"),
            "time_estimate": result.get("time_estimate", "?"),
        }

    async def create_obsidian_note(self, analysis: dict, relevance: dict, url: str) -> str:
        now      = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        slug     = re.sub(r"[^\w\s-]", "", analysis["title"].lower())
        slug     = re.sub(r"[\s_-]+", "-", slug).strip("-")[:60]
        filename = f"{date_str}-{slug}.md"

        if relevance["is_relevant"]:
            folder = OBSIDIAN_AI_FOLDER / analysis.get("content_type", "geral").title()
        else:
            folder = OBSIDIAN_INBOX / "Arquivo"
        folder.mkdir(parents=True, exist_ok=True)
        note_path = folder / filename

        tags = analysis.get("tags", [])
        tags.append("relevante" if relevance["is_relevant"] else "arquivado")
        tags_yaml = "\n".join(f"  - {t.lstrip('#')}" for t in tags)
        kp_md     = "\n".join(f"- {p}" for p in analysis.get("key_points", []))
        emoji     = {"read_now": "🟢", "bookmark": "🟡", "skip": "🔴", "follow_up": "🔵"}.get(
                        relevance.get("action", "bookmark"), "⚪")

        note = f"""---
title: "{analysis['title']}"
url: {url}
date: {date_str}
time: {time_str}
type: {analysis.get('content_type', 'article')}
difficulty: {analysis.get('difficulty', 'unknown')}
language: {analysis.get('language', 'en')}
read_time: {analysis.get('estimated_read_time', '?')} min
relevance_score: {relevance['score']}/10
action: {relevance.get('action', 'bookmark')}
ia_model: gemini-2.5-flash
tags:
{tags_yaml}
---

# {analysis['title']}

> {analysis['summary']}

## 🎯 Relevância para seus objetivos

{emoji} **Score:** {relevance['score']}/10 — {relevance.get('action', '').replace('_', ' ').title()}

**Análise:** {relevance['reason']}

---

## 📌 Pontos-chave

{kp_md}

---

## 🔗 Fonte

- **URL:** {url}
- **Capturado em:** {date_str} às {time_str}
- **Tipo:** {analysis.get('content_type', '?')} | **Dificuldade:** {analysis.get('difficulty', '?')}

---

## 💡 Conceitos mencionados

{', '.join(f'[[{c}]]' for c in analysis.get('concepts', []))}

---
*Nota criada pelo PKM Bot — Gemini 2.5 Flash (gratuito)*
"""
        note_path.write_text(note, encoding="utf-8")
        logger.info(f"Nota criada: {note_path}")
        return str(note_path.relative_to(OBSIDIAN_VAULT_PATH))

    def read_note(self, relative_path: str) -> Optional[str]:
        full = OBSIDIAN_VAULT_PATH / relative_path
        return full.read_text(encoding="utf-8") if full.exists() else None

    def delete_note(self, relative_path: str):
        full = OBSIDIAN_VAULT_PATH / relative_path
        if full.exists():
            full.unlink()

    def quota_status(self) -> str:
        total = self._flash_calls + self._lite_calls
        return f"Flash: {self._flash_calls} | Flash-Lite: {self._lite_calls} | Total hoje: {total}"

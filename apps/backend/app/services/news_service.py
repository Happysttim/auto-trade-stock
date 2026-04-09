from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

from ..config import Settings
from ..schemas import NewsArticle, NewsSelectionResult


TAG_RE = re.compile(r"<[^>]+>")
def _normalize_text(raw: str) -> str:
    cleaned = TAG_RE.sub(" ", raw or "")
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


class NewsService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _parse_published_at(self, entry: feedparser.FeedParserDict) -> datetime:
        for key in ("published", "updated"):
            if entry.get(key):
                try:
                    parsed = parsedate_to_datetime(entry[key])
                    if parsed.tzinfo is None:
                        return parsed.replace(tzinfo=timezone.utc)
                    return parsed.astimezone(timezone.utc)
                except Exception:
                    continue
        return datetime.now(timezone.utc)

    def _build_signature(self, articles: list[NewsArticle]) -> str:
        base = "||".join(f"{article.article_id}:{article.title}" for article in articles[:4])
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def collect_articles(self, *, previous_context_signature: str | None) -> NewsSelectionResult:
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(minutes=self.settings.news_lookback_minutes)
        recent_articles: list[NewsArticle] = []
        fallback_articles: list[NewsArticle] = []
        seen_ids: set[str] = set()

        for source in self.settings.news_sources:
            try:
                response = requests.get(source.url, timeout=self.settings.request_timeout_seconds)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
            except Exception:
                continue

            for entry in feed.entries[: self.settings.news_max_articles]:
                title = _normalize_text(entry.get("title", ""))
                url = entry.get("link", "")
                summary = _normalize_text(entry.get("summary", ""))
                published_at = self._parse_published_at(entry)
                article_id = hashlib.sha1(f"{title}|{url}".encode("utf-8")).hexdigest()
                if not title or not url or article_id in seen_ids:
                    continue

                seen_ids.add(article_id)
                article = NewsArticle(
                    article_id=article_id,
                    title=title,
                    source_name=source.name,
                    url=url,
                    published_at=published_at,
                    summary=summary,
                    region=source.region,
                    topic=source.topic,
                )
                fallback_articles.append(article)
                if published_at >= recent_cutoff:
                    recent_articles.append(article)

        recent_articles.sort(key=lambda item: item.published_at, reverse=True)
        fallback_articles.sort(key=lambda item: item.published_at, reverse=True)

        if recent_articles:
            selected = recent_articles[: self.settings.news_max_articles]
            return NewsSelectionResult(
                articles=selected,
                signature=self._build_signature(selected),
                mode="fresh",
            )

        selected = fallback_articles[: min(self.settings.news_max_articles, 4)]
        if not selected:
            return NewsSelectionResult(
                articles=[],
                signature="",
                mode="skip",
                skip_reason="No qualifying articles were returned from the configured sources.",
            )

        current_signature = self._build_signature(selected)
        if previous_context_signature and previous_context_signature == current_signature:
            return NewsSelectionResult(
                articles=[],
                signature=current_signature,
                mode="skip",
                skip_reason="Recent fallback articles are materially similar to the last analyzed context.",
            )

        return NewsSelectionResult(
            articles=selected,
            signature=current_signature,
            mode="fallback",
        )

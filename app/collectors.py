"""Collectors: GitHub Trending + Hacker News + RSS feeds."""

import logging
import math
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from db import insert_item

log = logging.getLogger("collectors")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

CATEGORIES = {
    "ai-ml":    ["llm", "gpt", "transformer", "neural", "inference",
                 "ml", "ai", "model", "training", "rag", "diffusion",
                 "embedding", "langchain", "openai", "anthropic", "ollama"],
    "security": ["cve", "vulnerability", "exploit", "security", "auth",
                 "zero-day", "supply-chain", "pentest", "malware", "firewall"],
    "infra":    ["kubernetes", "k8s", "docker", "terraform", "ansible",
                 "cloud", "aws", "gcp", "azure", "helm", "cilium",
                 "istio", "envoy", "proxmox", "containerd", "cni"],
    "tools":    ["cli", "tool", "framework", "library", "sdk", "plugin",
                 "extension", "editor", "terminal", "shell", "tui"],
}

HN_DOMAIN_WHITELIST = {
    "github.com", "arxiv.org", "blog.cloudflare.com", "kubernetes.io",
    "engineering.fb.com", "cloud.google.com", "aws.amazon.com",
    "openai.com", "anthropic.com", "huggingface.co",
}

HN_KEYWORD_RE = re.compile(
    r"\b(devops|infra|kubernetes|k8s|docker|cloud|aws|gcp|azure|"
    r"terraform|ansible|helm|ci/cd|pipeline|sre|observability|"
    r"ai|llm|gpt|ml|neural|model|training|inference|rag|"
    r"rust|go|python|wasm|linux|nixos|security|cve|exploit|"
    r"open.?source|self.?host)\b", re.IGNORECASE)


def categorize(title, description=""):
    text = f"{title} {description or ''}".lower()
    for cat, keywords in CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return cat
    return None


# ── GitHub Trending ──────────────────────────────────────────

async def collect_github():
    log.info("Collecting GitHub trending repos...")
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    now = datetime.now(timezone.utc)
    count = 0

    for window_days, min_stars in [(7, 500), (3, 100)]:
        since = (now - timedelta(days=window_days)).strftime("%Y-%m-%d")
        url = (
            "https://api.github.com/search/repositories"
            f"?q=created:>{since}+stars:>{min_stars}&sort=stars&per_page=30"
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            log.exception("GitHub API error (window=%dd)", window_days)
            continue

        for repo in data.get("items", []):
            created = datetime.fromisoformat(
                repo["created_at"].replace("Z", "+00:00"))
            days = max(1, (now - created).total_seconds() / 86400)
            velocity = repo["stargazers_count"] / days

            cat = categorize(repo["name"], repo.get("description", ""))
            if not cat:
                cat = "trending-repo"

            score = min(100, velocity / 5)

            insert_item(
                source="github",
                source_id=str(repo["id"]),
                url=repo["html_url"],
                title=repo["full_name"],
                description=repo.get("description", ""),
                score=score,
                velocity=velocity,
                category=cat,
                language=repo.get("language"),
                stars=repo["stargazers_count"],
                published_at=repo["created_at"],
            )
            count += 1

    log.info("GitHub: collected %d repos", count)


# ── Hacker News ──────────────────────────────────────────────

def _hn_is_relevant(item):
    title = item.get("title", "")
    url = item.get("url", "")
    if any(d in url for d in HN_DOMAIN_WHITELIST):
        return True
    if HN_KEYWORD_RE.search(title):
        return True
    return False


async def collect_hn():
    log.info("Collecting Hacker News top stories...")
    count = 0
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json")
            resp.raise_for_status()
            top_ids = resp.json()[:100]

            for item_id in top_ids:
                try:
                    r = await client.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
                    r.raise_for_status()
                    item = r.json()
                except Exception:
                    continue

                if not item or item.get("type") != "story":
                    continue
                if (item.get("score", 0) < 100
                        and not _hn_is_relevant(item)):
                    continue
                if not _hn_is_relevant(item) and item.get("score", 0) < 200:
                    continue

                hn_score = item.get("score", 0)
                descendants = item.get("descendants", 0)
                raw = hn_score * math.log(descendants + 2)
                score = min(100, raw / 50)

                url = item.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
                title = item.get("title", "")
                cat = categorize(title)

                published = datetime.fromtimestamp(
                    item.get("time", 0), tz=timezone.utc
                ).isoformat() if item.get("time") else None

                insert_item(
                    source="hn",
                    source_id=str(item_id),
                    url=url,
                    title=title,
                    description=f"{hn_score} points · {descendants} comments",
                    score=score,
                    velocity=0,
                    category=cat or "tools",
                    stars=hn_score,
                    published_at=published,
                )
                count += 1
    except Exception:
        log.exception("HN API error")

    log.info("HN: collected %d stories", count)


# ── RSS Feeds ────────────────────────────────────────────────

RSS_FEEDS = [
    ("https://www.cncf.io/blog/feed/", "cncf"),
    ("https://kubernetes.io/feed.xml", "k8s-blog"),
    ("https://lobste.rs/t/devops,ai,distributed.rss", "lobsters"),
    ("https://thenewstack.io/feed/", "thenewstack"),
    ("https://feed.infoq.com/devops/", "infoq"),
]


async def collect_rss():
    log.info("Collecting RSS feeds...")
    count = 0
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for feed_url, feed_name in RSS_FEEDS:
            try:
                resp = await client.get(feed_url)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
            except Exception:
                log.exception("RSS error: %s", feed_name)
                continue

            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                url = entry.get("link", "")
                if not url:
                    continue

                source_id = entry.get("id") or url
                description = entry.get("summary", "")
                if len(description) > 300:
                    description = description[:297] + "..."

                published = None
                for date_field in ("published_parsed", "updated_parsed"):
                    parsed = entry.get(date_field)
                    if parsed:
                        try:
                            published = datetime(*parsed[:6],
                                                 tzinfo=timezone.utc).isoformat()
                        except Exception:
                            pass
                        break

                cat = categorize(title, description)

                insert_item(
                    source="rss",
                    source_id=f"{feed_name}:{source_id}",
                    url=url,
                    title=title,
                    description=description,
                    score=50,
                    velocity=0,
                    category=cat or "infra",
                    published_at=published,
                )
                count += 1

    log.info("RSS: collected %d entries from %d feeds", count, len(RSS_FEEDS))


# ── Run all ──────────────────────────────────────────────────

async def collect_all():
    await collect_github()
    await collect_hn()
    await collect_rss()

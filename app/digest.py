"""Generate static index.html + feed.xml from Jinja2 template + DB items."""

import logging
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from db import get_items_for_digest, record_digest

log = logging.getLogger("digest")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
APP_DIR = Path(os.environ.get("APP_DIR", "/app"))


def _write_atomic(path, content):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _generate_rss(items, site_dir):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    entries = []
    for item in items[:30]:
        pub = item.get("published_at") or item.get("collected_at") or ""
        cat = escape(item.get("category") or "tools")
        desc = escape(item.get("description") or "")
        entries.append(
            f"    <item>\n"
            f"      <title>{escape(item['title'])}</title>\n"
            f"      <link>{escape(item['url'])}</link>\n"
            f"      <description>{desc}</description>\n"
            f"      <category>{cat}</category>\n"
            f"      <guid isPermaLink=\"false\">{escape(item.get('source',''))}:{escape(item.get('source_id',''))}</guid>\n"
            f"    </item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        '  <channel>\n'
        '    <title>elflab.eu — DevOps &amp; AI Radar</title>\n'
        '    <link>https://elflab.eu</link>\n'
        '    <description>Curated DevOps, AI, and infrastructure news</description>\n'
        '    <language>en</language>\n'
        f'    <lastBuildDate>{now}</lastBuildDate>\n'
        '    <atom:link href="https://elflab.eu/feed.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(entries) + "\n"
        '  </channel>\n'
        '</rss>\n'
    )
    _write_atomic(site_dir / "feed.xml", xml)
    log.info("RSS feed written (%d items)", len(entries))


def generate_digest():
    items = get_items_for_digest(limit=60, hours=72)
    log.info("Generating digest with %d items", len(items))

    site_dir = DATA_DIR / "site"
    site_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(APP_DIR)))
    template = env.get_template("index.jinja2")

    categories = {}
    for item in items:
        cat = item.get("category") or "tools"
        categories.setdefault(cat, 0)
        categories[cat] += 1

    html = template.render(
        items=items,
        categories=sorted(categories.keys()),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total_count=len(items),
    )

    _write_atomic(site_dir / "index.html", html)
    _generate_rss(items, site_dir)

    record_digest(len(items))
    log.info("Digest written to %s (%d bytes)", site_dir / "index.html", len(html))

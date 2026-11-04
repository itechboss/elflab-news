"""Generate static index.html from Jinja2 template + DB items."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from db import get_items_for_digest, record_digest

log = logging.getLogger("digest")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
APP_DIR = Path(os.environ.get("APP_DIR", "/app"))


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

    out = site_dir / "index.html"
    tmp = site_dir / "index.html.tmp"
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(out)

    record_digest(len(items))
    log.info("Digest written to %s (%d bytes)", out, len(html))

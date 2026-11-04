"""elflab-news — curated DevOps/AI/Infra news feed."""

import asyncio
import logging
import os
from pathlib import Path

from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
from collectors import collect_all
from digest import generate_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("main")

DATA_DIR = os.environ.get("DATA_DIR", "/data")
PORT = int(os.environ.get("PORT", "8080"))


async def run_collect_and_digest():
    try:
        await collect_all()
        generate_digest()
    except Exception:
        log.exception("collect+digest failed")


async def index_handler(request):
    index = Path(DATA_DIR) / "site" / "index.html"
    if index.exists():
        return web.FileResponse(index)
    return web.Response(
        text="<h1>elflab.eu</h1><p>First digest is being generated...</p>",
        content_type="text/html",
    )


async def feed_handler(request):
    feed = Path(DATA_DIR) / "site" / "feed.xml"
    if feed.exists():
        return web.FileResponse(feed,
                                headers={"Content-Type": "application/rss+xml"})
    return web.Response(text="Feed not ready", status=503)


async def health(request):
    return web.Response(text="ok")


async def on_startup(app):
    log.info("Running initial collect + digest...")
    await run_collect_and_digest()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_collect_and_digest, "interval", hours=1,
                      id="collect-digest")
    scheduler.start()
    app["scheduler"] = scheduler
    log.info("Scheduler started: collect+digest every 1h")


async def on_cleanup(app):
    if "scheduler" in app:
        app["scheduler"].shutdown(wait=False)


app = web.Application()
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)
app.router.add_get("/", index_handler)
app.router.add_get("/feed.xml", feed_handler)
app.router.add_get("/healthz", health)

if __name__ == "__main__":
    db.init_db(DATA_DIR)
    log.info("elflab-news starting on :%d", PORT)
    web.run_app(app, host="0.0.0.0", port=PORT)

"""Scout: watches lab blogs and feeds and stores new, deduplicated items."""
import ipaddress
import json
import re
import socket
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

from . import db
from .paths import SEEDS, SOURCES

UA = {"User-Agent": "Mozilla/5.0 (FrontierLineage research bot)"}


def load_sources():
    return json.loads(SOURCES.read_text())["sources"]


def _public_only(request):
    """Refuse to fetch loopback, private, link-local or reserved addresses, including on redirects."""
    if request.url.scheme not in ("http", "https"):
        raise ValueError(f"refusing to fetch {request.url.scheme} URL")
    for *_, addr in socket.getaddrinfo(request.url.host, request.url.port or 443):
        ip = ipaddress.ip_address(addr[0])
        if not ip.is_global:
            raise ValueError(f"refusing to fetch non-public address {ip}")


def _get(url):
    with httpx.Client(headers=UA, timeout=20, follow_redirects=True, event_hooks={"request": [_public_only]}) as c:
        r = c.get(url)
    r.raise_for_status()
    return r.text


def article_text(html, limit=12000):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "svg", "form"]):
        tag.decompose()
    node = soup.find("article") or soup.find("main") or soup.body or soup
    text = re.sub(r"\n\s*\n+", "\n\n", node.get_text("\n"))
    return re.sub(r"[ \t]+", " ", text).strip()[:limit]


def list_source(src, limit):
    if src["type"] == "rss":
        feed = feedparser.parse(_get(src["url"]))
        return [{"title": e.get("title", ""), "url": e.get("link", ""), "published": e.get("published", "")} for e in feed.entries[:limit]]
    soup = BeautifulSoup(_get(src["url"]), "html.parser")
    pat = re.compile(src["link_pattern"])
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0].split("#")[0]
        if href.startswith(src["base"]):
            href = href[len(src["base"]):]
        if pat.match(href) and href not in seen:
            seen.add(href)
            title = " ".join(a.get_text(" ").split())[:200]
            out.append({"title": title, "url": urljoin(src["base"], href), "published": ""})
    return out[:limit]


def _store(source, lab, title, url, published, text):
    if db.one("SELECT id FROM items WHERE url=?", (url,)):
        return None
    return db.insert("items", source=source, lab=lab, title=title, url=url, published=published, fetched_at=db.now(), text=text)


def scout_live(per_source=5, log=print):
    new = []
    for src in load_sources():
        try:
            entries = list_source(src, per_source)
        except Exception as e:
            log(f"scout: {src['id']} failed: {e}")
            continue
        for e in entries:
            if not e["url"] or db.one("SELECT id FROM items WHERE url=?", (e["url"],)):
                continue
            try:
                html = _get(e["url"])
                text = article_text(html)
                title = e["title"] or (BeautifulSoup(html, "html.parser").title or {}).get_text("").strip()
            except Exception as ex:
                log(f"scout: fetch {e['url']} failed: {ex}")
                continue
            item_id = _store(src["id"], src["lab"], title, e["url"], e["published"], text)
            if item_id:
                new.append(item_id)
        log(f"scout: {src['id']} done")
    return new


def scout_seeds():
    data = json.loads(SEEDS.read_text())
    return [i for i in (_store("seed", s["lab"], s["title"], s["url"], s["published"], s["text"]) for s in data["items"]) if i]


def ingest_url(url, lab="Manual"):
    existing = db.one("SELECT id FROM items WHERE url=?", (url,))
    if existing:
        return existing["id"]
    html = _get(url)
    title = (BeautifulSoup(html, "html.parser").title or {}).get_text("").strip() if BeautifulSoup(html, "html.parser").title else url
    return _store("manual", lab, title, url, "", article_text(html))

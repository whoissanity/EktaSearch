from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import aiohttp
try:
    from curl_cffi.requests import AsyncSession as CurlSession  # type: ignore
    _CURL_AVAILABLE = True
except Exception:
    CurlSession = None  # type: ignore
    _CURL_AVAILABLE = False
    
from bs4 import BeautifulSoup
from sqlalchemy import select, text

from app.db.database import AsyncSessionLocal
from app.db.models import Category
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
if not _CURL_AVAILABLE:
    logger.warning("[scrape] tls_fingerprint_client_unavailable")

SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "prewarm_snapshot.json"

SITE_HOMEPAGES: dict[str, list[str]] = {
    "startech": ["https://www.startech.com.bd"],
    "skyland": ["https://www.skyland.com.bd"],
    "techland": ["https://www.techlandbd.com", "https://www.techlandbd.com/pc-components"],
    "ryans": ["https://www.ryans.com", "https://www.ryans.com/category", "https://www.ryanscomputers.com"],
    "potaka": ["https://potakait.com"],
    "techdiversity": ["https://techdiversitybd.com"],
    "vibe": ["https://vibegaming.com.bd"],
    "blisstronics": ["https://blisstronics.com"],
}

SITE_CATEGORY_FALLBACKS: dict[str, list[str]] = {
    "techland": [
        "https://www.techlandbd.com/pc-components/processor",
        "https://www.techlandbd.com/pc-components/motherboard",
        "https://www.techlandbd.com/pc-components/graphics-card",
        "https://www.techlandbd.com/pc-components/computer-ram",
        "https://www.techlandbd.com/pc-components/solid-state-drive",
        "https://www.techlandbd.com/pc-components/power-supply",
        "https://www.techlandbd.com/shop-laptop-notebook",
        "https://www.techlandbd.com/gaming-laptop",
        "https://www.techlandbd.com/mechanical-keyboard",
        "https://www.techlandbd.com/gaming-mouse",
    ],
    "ryans": [
        "https://www.ryans.com/category/desktop-component-processor",
        "https://www.ryans.com/category/desktop-component-motherboard",
        "https://www.ryans.com/category/desktop-component-graphics-card",
        "https://www.ryans.com/category/desktop-component-desktop-ram",
        "https://www.ryans.com/category/desktop-component-casing",
        "https://www.ryans.com/category/desktop-component-power-supply",
        "https://www.ryans.com/category/desktop-component-cpu-cooler",
        "https://www.ryans.com/category/desktop-component-ssd",
        "https://www.ryans.com/category/laptop-all-laptop",
        "https://www.ryans.com/category/monitor-all-monitor",
    ],
}


_BLOCK_PATH_PARTS = {
    "cart",
    "login",
    "signin",
    "sign-in",
    "signup",
    "sign-up",
    "register",
    "blog",
    "support",
    "help",
    "faq",
    "privacy",
    "policy",
    "terms",
    "contact",
    "about",
    "cdn-cgi",
    "email-protection",
}
_BAD_QUERY_KEYS = {"sort", "filter", "orderby"}
_CATEGORY_HINTS = ("category", "product-category")
_CATEGORY_TEXT_HINTS = ()


def _canonicalize(url: str, *, keep_query: bool = True, keep_query_keys: set[str] | None = None) -> str:
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    if scheme in {"http", "https"}:
        scheme = "https"

    netloc = parsed.netloc.lower()
    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    if netloc.endswith(":443"):
        netloc = netloc[:-4]

    path = parsed.path.rstrip("/") or "/"

    query = ""
    if keep_query:
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if keep_query_keys is not None:
            allowed = {k.lower() for k in keep_query_keys}
            kept = [(k, v) for k, v in pairs if k.lower() in allowed]
        else:
            kept = [(k, v) for k, v in pairs if k.lower() not in _BAD_QUERY_KEYS]
        query = urlencode(kept)

    return urlunparse((scheme, netloc, path, "", query, ""))


def _canonicalize_product_url(url: str) -> str:
    # Products must not be duplicated due to query params/fragments.
    return _canonicalize(url, keep_query=False)


def _title_norm(title: str) -> str:
    # "RTX 4070 TI OC" == "rtx 4070 ti oc"
    return " ".join((title or "").split()).strip().lower()


def _is_blocked_url(url: str, homepage: str) -> bool:
    parsed = urlparse(url)
    home = urlparse(homepage)
    if parsed.netloc.lower() != home.netloc.lower():
        return True
    p = parsed.path.lower()
    if any(x in p for x in _BLOCK_PATH_PARTS):
        return True
    if any(k.lower() in _BAD_QUERY_KEYS for k, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        return True
    return False


def _looks_category_url(url: str) -> bool:
    p = urlparse(url).path.lower()
    return any(h in p for h in _CATEGORY_HINTS)


def _looks_category_anchor(text: str, url: str) -> bool:
    t = " ".join((text or "").split()).strip().lower()
    if not t:
        return False
    # Skip tiny or utility nav labels.
    if t in {"home", "shop", "all", "menu", "offers", "deals"}:
        return False
    if any(h in t for h in _CATEGORY_TEXT_HINTS):
        return True
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return False
    # Accept broad category/subcategory URLs from navbar, not just PC parts.
    if len(path.split("/")) >= 1:
        return True
    return _looks_category_url(url)


def _looks_product_title(text: str) -> bool:
    t = " ".join((text or "").split()).strip()
    if len(t) < 8:
        return False
    if "%" in t and len(t) <= 20:
        return False
    if t.replace("-", "").replace("_", "").isdigit():
        return False
    return any(ch.isalpha() for ch in t)


def _extract_price_value(card_text: str, card_node) -> int | None:
    txt = " ".join((card_text or "").split())
    patterns = [
        r"(?:৳|Tk\.?|BDT)\s*([0-9][0-9,\s]*(?:\.[0-9]{1,2})?)",
        r"([0-9][0-9,\s]{2,})\s*(?:৳|Tk\.?|BDT)",
    ]
    for pat in patterns:
        m = re.search(pat, txt, flags=re.I)
        if m:
            raw = m.group(1).replace(",", "").replace(" ", "")
            try:
                val = int(float(raw))
                if 1 <= val <= 10_000_000:
                    return val
            except ValueError:
                pass

    # Fallback: inspect common price-bearing attributes.
    for attr in ("data-price", "data-amount", "content", "value"):
        v = card_node.get(attr) if hasattr(card_node, "get") else None
        if not v:
            continue
        raw = str(v).replace(",", "").strip()
        if raw.replace(".", "", 1).isdigit():
            val = int(float(raw))
            if 1 <= val <= 10_000_000:
                return val
    return None


def _sanitize_product_row(row: dict) -> dict | None:
    url = str(row.get("url") or "").strip()
    title = " ".join(str(row.get("title") or "").split()).strip()
    if not url or not title or not _looks_product_title(title):
        return None

    # Prevent data URI blobs from exploding DB size.
    image = row.get("image")
    if isinstance(image, str) and image.strip().lower().startswith("data:"):
        image = None
    if isinstance(image, str) and len(image) > 1000:
        image = image[:1000]

    price = row.get("price")
    if isinstance(price, (int, float)):
        p = int(price)
        if p <= 0 or p > 10_000_000:
            price = None
        else:
            price = p
    else:
        price = None

    review_count = row.get("review_count")
    if isinstance(review_count, (int, float)):
        rc = int(review_count)
        if rc < 0 or rc > 10_000_000:
            review_count = None
        else:
            review_count = rc
    else:
        review_count = None

    out = dict(row)
    out["title"] = title[:600]
    out["price"] = price
    out["review_count"] = review_count
    out["image"] = image
    out["url"] = _canonicalize_product_url(url)
    out["_title_norm"] = _title_norm(title)
    return out


def _extract_products_from_html(html: str, base_url: str, site: str, category_name: str, subcategory_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    cards = soup.select(
        "li.product, div.product, div.product-item, div.product-thumb, div.product-wrapper, div.category-single-product, div.wd-product-wrapper, div.p-item, div.h-full > div.bg-white"
    )
    for c in cards:
        anchors = c.select("a[href]")
        if not anchors:
            continue
        best_a = None
        best_title = ""
        for a in anchors:
            t = a.get_text(" ", strip=True)
            if _looks_product_title(t) and len(t) > len(best_title):
                best_title = t
                best_a = a
        if best_a is None:
            continue
        title = best_title
        href = _canonicalize_product_url(urljoin(base_url, best_a.get("href", "")))
        if href == _canonicalize_product_url(base_url):
            continue
        if any(x in urlparse(href).path.lower() for x in _BLOCK_PATH_PARTS):
            continue
        txt = c.get_text(" ", strip=True)
        price = _extract_price_value(txt, c)
        in_stock_text = txt.lower()
        in_stock = not any(x in in_stock_text for x in ("out of stock", "stock out", "unavailable"))
        img = c.select_one("img[src], img[data-src]")
        image = None
        if img:
            image = urljoin(base_url, img.get("src") or img.get("data-src") or "")
        out.append(
            {
                "site": site,
                "title": title[:600],
                "brand": None,
                "category": category_name[:255] if category_name else None,
                "subcategory": subcategory_name[:255] if subcategory_name else None,
                "price": price,
                "currency": "BDT",
                "url": href,
                "image": image[:1000] if image else None,
                "in_stock": in_stock,
                "rating": None,
                "review_count": None,
            }
        )
    return out


def _browser_like_headers(url: str, referer: str | None = None) -> dict[str, str]:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer and urlparse(referer).netloc == parsed.netloc else "none",
        "Sec-Fetch-User": "?1",
        "Referer": referer or origin,
    }


async def _fetch_text(
    session: aiohttp.ClientSession,
    url: str,
    *,
    site: str = "",
    referer: str | None = None,
) -> tuple[int, str]:
    timeout = aiohttp.ClientTimeout(total=20)
    headers = _browser_like_headers(url, referer=referer)

    if _CURL_AVAILABLE and site in {"ryans", "skyland"}:
        async with CurlSession(impersonate="chrome124", timeout=25) as s:  # type: ignore[misc]
            r = await s.get(url, headers=headers, allow_redirects=True)
            return int(r.status_code), (r.text or "")

    # Retry with increasing backoff for anti-bot statuses.
    for attempt in range(3):
        async with session.get(url, timeout=timeout, headers=headers, allow_redirects=True) as r:
            txt = await r.text()
            status = r.status
            if status >= 500:
                r.raise_for_status()

        if status in {403, 429} and attempt < 2:
            delay = 1.5 if attempt == 0 else 5.0
            await asyncio.sleep(delay + random.random() * 0.8)
            continue
        if status >= 400:
            logger.warning("[scrape] http_%s url=%s", status, url)
        return status, txt
    return 0, ""


async def _fetch_first_available_homepage(
    session: aiohttp.ClientSession,
    site: str,
    candidates: list[str],
) -> tuple[str, str] | None:
    for u in candidates:
        try:
            status, html = await _fetch_text(session, u, site=site, referer=u)
            if status >= 400:
                continue
            # Don't accept obvious challenge/error pages if we still have candidates.
            low = (html or "").lower()
            if any(mark in low for mark in ("access denied", "forbidden", "just a moment", "captcha")):
                continue
            return u, html
        except Exception:
            continue
    logger.warning("[scrape] unable to fetch homepage site=%s tried=%s", site, len(candidates))
    return None


async def _upsert_category(
    site: str,
    name: str,
    url: str,
    parent_id: int | None,
    *,
    need_id: bool = False,
) -> int | None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                """
                INSERT INTO categories(site, name, parent_id, url)
                VALUES (:site, :name, :parent_id, :url)
                ON CONFLICT(url) DO UPDATE
                SET site=excluded.site, name=excluded.name, parent_id=excluded.parent_id
                """
            ),
            {"site": site, "name": name[:255], "parent_id": parent_id, "url": url},
        )
        await db.commit()
        if not need_id:
            return None
        row = await db.execute(select(Category.id).where(Category.url == url))
        return row.scalar_one_or_none()


async def _all_category_urls_for_site(site: str) -> list[tuple[str, str, str]]:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            text(
                """
                SELECT c.url, c.name, COALESCE(p.name, '')
                FROM categories c
                LEFT JOIN categories p ON p.id = c.parent_id
                WHERE c.site = :site
                """
            ),
            {"site": site},
        )
        return [(r[0], r[1] or "", r[2] or "") for r in rows.fetchall()]


async def _upsert_products(products: list[dict]) -> int:
    if not products:
        return 0
    async with AsyncSessionLocal() as db:
        accepted = 0
        for p in products:
            cleaned = _sanitize_product_row(p)
            if cleaned is None:
                continue
            # Avoid DB growth: if another URL yields the exact same title (case-insensitive),
            # treat it as a duplicate and skip inserting a new row.
            site = cleaned.get("site")
            tnorm = cleaned.get("_title_norm") or ""
            if site and tnorm:
                dupe_row = await db.execute(
                    text(
                        """
                        SELECT url
                        FROM products
                        WHERE site = :site AND lower(title) = :title_lc
                        LIMIT 1
                        """
                    ),
                    {"site": site, "title_lc": tnorm},
                )
                existing_url = dupe_row.scalar_one_or_none()
                if existing_url and _canonicalize_product_url(existing_url) != cleaned["url"]:
                    continue

            await db.execute(
                text(
                    """
                    INSERT INTO products(site, title, brand, category, subcategory, price, currency, url, image, in_stock, rating, review_count)
                    VALUES (:site, :title, :brand, :category, :subcategory, :price, :currency, :url, :image, :in_stock, :rating, :review_count)
                    ON CONFLICT(url) DO UPDATE
                    SET price=excluded.price,
                        in_stock=excluded.in_stock,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE products.price IS NOT excluded.price
                       OR products.in_stock IS NOT excluded.in_stock
                    """
                ),
                {k: v for k, v in cleaned.items() if not str(k).startswith("_")},
            )
            accepted += 1
        await db.commit()
    return accepted


async def _latest_products_updated_at_epoch() -> int | None:
    async with AsyncSessionLocal() as db:
        row = await db.execute(text("SELECT MAX(updated_at) FROM products"))
        value = row.scalar_one_or_none()
        if value is None:
            return None
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())


async def _products_row_count() -> int:
    async with AsyncSessionLocal() as db:
        row = await db.execute(text("SELECT COUNT(1) FROM products"))
        return int(row.scalar_one() or 0)


def _extract_nav_categories(html: str, homepage: str, site: str) -> list[tuple[str, str, str | None, str | None]]:
    soup = BeautifulSoup(html, "lxml")
    out: list[tuple[str, str, str | None, str | None]] = []
    seen: set[str] = set()

    def _push(name: str, url: str, parent_name: str | None, parent_url: str | None) -> None:
        href = _canonicalize(urljoin(homepage, url))
        if href in seen:
            return
        seen.add(href)
        if _is_blocked_url(href, homepage) or not _looks_category_anchor(name, href):
            return
        out.append((name[:255], href, parent_name[:255] if parent_name else None, _canonicalize(parent_url) if parent_url else None))

    if site == "ryans":
        # Ryans megamenu structure (from your provided HTML):
        # <nav id="navbar_main"> ... <li class="nav-item dropdown has-megamenu">
        #   <button class="nav-link main-nav-link">Laptop</button>
        #   <div class="dropdown-menu megamenu"> ... <a href=".../category/...">Acer</a>
        nav = soup.select_one("nav#navbar_main") or soup
        for item in nav.select("li.has-megamenu"):
            btn = item.select_one("button.main-nav-link, a.main-nav-link")
            parent_name = (btn.get_text(" ", strip=True) if btn else "") or None
            menu = item.select_one(".dropdown-menu.megamenu")
            if not parent_name or not menu:
                continue

            anchors = menu.select("a[href]")
            if not anchors:
                continue

            # Try to find a reasonable URL representing the parent category.
            parent_href = None
            for a in anchors:
                href = a.get("href", "")
                if "/category/" not in href:
                    continue
                t = a.get_text(" ", strip=True).lower()
                if "all" in t or a.has_attr("class") and "fw-bold" in (a.get("class") or []):
                    parent_href = href
                    break
            if parent_href is None:
                for a in anchors:
                    href = a.get("href", "")
                    if "/category/" in href:
                        parent_href = href
                        break

            if parent_href:
                _push(parent_name, parent_href, None, None)
                parent_url = _canonicalize(urljoin(homepage, parent_href))
            else:
                parent_url = None

            for a in anchors:
                href = a.get("href", "")
                if not href:
                    continue
                if "/category/" not in href:
                    continue
                child_name = a.get_text(" ", strip=True) or urlparse(href).path.strip("/").split("/")[-1].replace("-", " ")
                _push(child_name, href, parent_name, parent_url)

        return out

    if site == "techland":
        # Techland nested menu (from your provided HTML): <nav class="... nav-menu">
        nav = soup.select_one("nav.nav-menu") or soup.select_one("nav .nav-menu") or soup

        # Top-level items are big block links; nested items live in ul.submenu li.menu-item.
        for top_li in nav.select("ul > li.menu-item, li.menu-item"):
            top_a = top_li.select_one(":scope > a[href]")
            if not top_a:
                continue
            top_name = top_a.get_text(" ", strip=True)
            top_href = top_a.get("href", "")
            if not top_name or not top_href:
                continue
            _push(top_name, top_href, None, None)
            top_url = _canonicalize(urljoin(homepage, top_href))

            # Walk descendants: for each <li.menu-item><a ...> build parent chain via nearest ancestor li.menu-item > a.
            for child_li in top_li.select("ul.submenu li.menu-item"):
                child_a = child_li.select_one(":scope > a[href]")
                if not child_a:
                    continue
                child_name = child_a.get_text(" ", strip=True)
                child_href = child_a.get("href", "")
                if not child_name or not child_href:
                    continue

                # Determine parent as the closest ancestor menu-item with a direct anchor.
                parent_li = child_li.find_parent("li", class_="menu-item")
                parent_a = None
                if parent_li and parent_li is not top_li:
                    parent_a = parent_li.select_one(":scope > a[href]")
                if parent_a:
                    p_name = parent_a.get_text(" ", strip=True) or top_name
                    p_url = _canonicalize(urljoin(homepage, parent_a.get("href", "")))
                else:
                    p_name = top_name
                    p_url = top_url

                _push(child_name, child_href, p_name, p_url)

        return out

    nav_roots = soup.select("nav, header, .navbar, .menu, .main-menu")
    if not nav_roots:
        nav_roots = [soup]
    for root in nav_roots:
        for a in root.select("a[href]"):
            href = urljoin(homepage, a.get("href", ""))
            href = _canonicalize(href)
            if href in seen:
                continue
            seen.add(href)
            if _is_blocked_url(href, homepage) or not _looks_category_anchor(a.get_text(" ", strip=True), href):
                continue
            name = a.get_text(" ", strip=True) or urlparse(href).path.strip("/").replace("-", " ")
            parent = None
            parent_url = None
            li = a.find_parent("li")
            if li:
                pnode = li.find_parent("li")
                if pnode:
                    pa = pnode.select_one("a[href]")
                    if pa:
                        parent = pa.get_text(" ", strip=True) or None
                        parent_url = _canonicalize(urljoin(homepage, pa.get("href", "")))
            out.append((name[:255], href, parent[:255] if parent else None, parent_url))
    return out


def _listing_pages_for_category(base_url: str, max_pages: int = 8) -> list[str]:
    parsed = urlparse(base_url)
    pages = []
    for page in range(1, max_pages + 1):
        if page == 1:
            pages.append(base_url)
            continue
        query = parse_qsl(parsed.query, keep_blank_values=True)
        query = [(k, v) for k, v in query if k.lower() != "page"]
        query.append(("page", str(page)))
        url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(query), ""))
        pages.append(_canonicalize(url, keep_query=True, keep_query_keys={"page"}))
    return pages


def _is_probable_product_detail_page(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    card_count = len(
        soup.select(
            "li.product, div.product, div.product-item, div.product-thumb, div.product-wrapper, div.category-single-product, div.wd-product-wrapper, div.p-item"
        )
    )
    has_buy_cta = bool(
        soup.select_one(
            "button[id*='add'], button[class*='add'], .add-to-cart, [data-add-to-cart], .product-buy, .buy-now"
        )
    )
    has_product_meta = bool(
        soup.select_one("meta[property='og:type'][content*='product'], .product-title, .product-name, [itemprop='sku']")
    )
    return card_count <= 2 and has_buy_cta and has_product_meta


def _has_real_listing_pagination(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one("ul.pagination, .pagination, .pager, a[rel='next']"):
        return True
    if soup.select_one("a[href*='?page=2'], a[href*='&page=2']"):
        return True
    return False


async def discover_and_scrape_once() -> dict:
    cycle_t0 = time.perf_counter()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
    }
    result: dict = {"generated_at": int(time.time()), "sites": {}, "products_upserted": 0}
    logger.info("[scrape] ==== cycle start | sites=%s ====", len(SITE_HOMEPAGES))
    connector = aiohttp.TCPConnector(limit=40, ttl_dns_cache=300)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        ordered_sites = ["techland", "ryans"]
        site_items = list(SITE_HOMEPAGES.items())
        site_items.sort(key=lambda kv: (0 if kv[0] in ordered_sites else 1, ordered_sites.index(kv[0]) if kv[0] in ordered_sites else 999, kv[0]))
        total_sites = len(site_items)
        for idx, (site, homepage_candidates) in enumerate(site_items, start=1):
            site_t0 = time.perf_counter()
            logger.info("[scrape] [%s/%s] %s: start", idx, total_sites, site)
            discovered: set[str] = set()
            products: list[dict] = []

            resolved = await _fetch_first_available_homepage(session, site, homepage_candidates)
            if resolved is None:
                continue
            homepage, homepage_html = resolved
            site_sem = asyncio.Semaphore(3 if site in {"ryans", "skyland", "techland"} else 12)

            nav_entries = _extract_nav_categories(homepage_html, homepage, site)
            # Some sites render navbar via JS; fallback to whole-document anchor scan.
            if not nav_entries:
                soup = BeautifulSoup(homepage_html, "lxml")
                seen = set()
                for a in soup.select("a[href]"):
                    href = _canonicalize(urljoin(homepage, a.get("href", "")))
                    if href in seen:
                        continue
                    seen.add(href)
                    txt = a.get_text(" ", strip=True)
                    if _is_blocked_url(href, homepage) or not _looks_category_anchor(txt, href):
                        continue
                    nav_entries.append((txt[:255] or urlparse(href).path.strip("/")[:255], href, None, None))
            # Site-specific hard fallback when navbar is empty/unreliable.
            if not nav_entries and site in SITE_CATEGORY_FALLBACKS:
                for u in SITE_CATEGORY_FALLBACKS[site]:
                    href = _canonicalize(u)
                    if _is_blocked_url(href, homepage):
                        continue
                    name = urlparse(href).path.strip("/").split("/")[-1].replace("-", " ").title()[:255]
                    nav_entries.append((name, href, None, None))
            parent_map_by_url: dict[str, int] = {}
            for name, url, parent_name, parent_url in nav_entries:
                discovered.add(url)
                if parent_name is None:
                    pid = await _upsert_category(site, name, url, None, need_id=True)
                    if pid is not None:
                        parent_map_by_url[_canonicalize(url)] = pid
                else:
                    parent_id = parent_map_by_url.get(_canonicalize(parent_url or ""))
                    if parent_id is None:
                        if parent_url and not _is_blocked_url(parent_url, homepage):
                            parent_id = await _upsert_category(site, parent_name, parent_url, None, need_id=True)
                        if parent_id is not None:
                            parent_map_by_url[_canonicalize(parent_url or "")] = parent_id
                    await _upsert_category(site, name, url, parent_id, need_id=False)

            stored_categories = await _all_category_urls_for_site(site)
            max_pages = max(1, int(settings.scrape_max_pages_per_category))

            async def scrape_category(category_url: str, category_name: str, parent_name: str):
                pages = _listing_pages_for_category(category_url, max_pages=max_pages)
                prev_url = homepage
                consecutive_404 = 0
                allow_pagination = True
                for i, page_url in enumerate(pages):
                    if _is_blocked_url(page_url, homepage):
                        continue
                    async with site_sem:
                        try:
                            status, html = await _fetch_text(
                                session,
                                page_url,
                                site=site,
                                referer=prev_url,
                            )
                        except Exception:
                            return
                    prev_url = page_url
                    if status == 404:
                        consecutive_404 += 1
                        if consecutive_404 >= 2:
                            break
                        continue
                    if status >= 400:
                        continue
                    consecutive_404 = 0

                    if i == 0:
                        if _is_probable_product_detail_page(html):
                            # Mis-classified category URL (single product page): do not paginate it.
                            return
                        allow_pagination = _has_real_listing_pagination(html)

                    rows = _extract_products_from_html(
                        html,
                        page_url,
                        site=site,
                        category_name=parent_name or category_name,
                        subcategory_name=category_name if parent_name else "",
                    )
                    products.extend(rows)

                    # No real pagination detected -> only first page is valid.
                    if i == 0 and not allow_pagination:
                        break
                    # If a later page has no products, stop paging this category.
                    if i > 0 and not rows:
                        break
                    if site == "techland" and i < len(pages) - 1:
                        await asyncio.sleep(random.uniform(1.0, 2.5))

            jobs = []
            for category_url, category_name, parent_name in stored_categories:
                jobs.append(scrape_category(category_url, category_name, parent_name))
            logger.info(
                "[scrape] [%s/%s] %s: categories=%s listing_pages=%s",
                idx,
                total_sites,
                site,
                len(stored_categories),
                len(stored_categories) * max_pages,
            )
            await asyncio.gather(*jobs)

            by_link = {}
            for p in products:
                by_link[p["url"]] = p
            upserted = await _upsert_products(list(by_link.values()))
            result["products_upserted"] += upserted
            result["sites"][site] = {
                "discovered_urls": sorted(discovered),
                "stored_category_urls": [x[0] for x in stored_categories],
                "products": list(by_link.values()),
                "upserted": upserted,
            }
            logger.info(
                "[scrape] [%s/%s] %s: done products=%s upserted=%s took=%ss",
                idx,
                total_sites,
                site,
                len(by_link),
                upserted,
                round(time.perf_counter() - site_t0, 1),
            )

    SNAPSHOT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "[scrape] ==== cycle done | site_count=%s upserted_total=%s took=%ss ====",
        len(result.get("sites", {})),
        result.get("products_upserted", 0),
        round(time.perf_counter() - cycle_t0, 1),
    )
    return result


async def run_full_scrape() -> dict:
    """Single full cycle: navbar category discovery + product upsert."""
    return await discover_and_scrape_once()


async def run_full_scrape_if_stale(max_age_seconds: int = 3600, *, force: bool = False) -> dict:
    now_epoch = int(time.time())
    last_updated = await _latest_products_updated_at_epoch()
    product_count = await _products_row_count()
    if force:
        logger.info("[scrape] force_run=true -> scraping_now")
    if (not force) and product_count > 0 and last_updated is not None and (now_epoch - last_updated) < max_age_seconds:
        age = now_epoch - last_updated
        left = max_age_seconds - age
        logger.info(
            "[scrape] skip_fresh_data age_seconds=%s threshold_seconds=%s next_scrape_in_seconds=%s",
            age,
            max_age_seconds,
            left,
        )
        return {
            "ran": False,
            "reason": "fresh_data",
            "last_updated_epoch": last_updated,
            "products_upserted": 0,
            "sites": {},
        }
    logger.info(
        "[scrape] stale_or_empty_data last_updated_epoch=%s product_count=%s threshold_seconds=%s -> scraping_now",
        last_updated,
        product_count,
        max_age_seconds,
    )
    data = await run_full_scrape()
    data["ran"] = True
    return data


async def run_prewarm_forever(interval_seconds: int = 3600, *, run_immediately: bool = True) -> None:
    if not run_immediately:
        await asyncio.sleep(max(300, interval_seconds))
    while True:
        try:
            await run_full_scrape_if_stale(max_age_seconds=3600)
        except Exception as e:
            logger.warning("prewarm cycle failed: %s", e)
        await asyncio.sleep(max(300, interval_seconds))

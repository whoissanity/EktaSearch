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
from app.core.logger import scrape_log

logger = logging.getLogger(__name__)
settings = get_settings()
if not _CURL_AVAILABLE:
    logger.warning("[scrape] tls_fingerprint_client_unavailable")

SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "prewarm_snapshot.json"

SITE_HOMEPAGES: dict[str, list[str]] = {
    "ryans": ["https://www.ryans.com", "https://www.ryans.com/category", "https://www.ryanscomputers.com"],
    "startech": ["https://www.startech.com.bd"],
    "skyland": ["https://www.skyland.com.bd/", "https://skyland.com.bd/", "https://www.skyland.com.bd"],
    "techland": ["https://www.techlandbd.com", "https://www.techlandbd.com/pc-components"],
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
        "https://www.techlandbd.com/pc-components/solid-state-drive",
        "https://www.techlandbd.com/pc-components/power-supply",
        "https://www.techlandbd.com/gaming-laptop",
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
_STANDARD_CATEGORY_MAP = {
    "processor": "CPU",
    "cpu": "CPU",
    "graphics card": "GPU",
    "gpu": "GPU",
    "motherboard": "Motherboard",
    "ram": "RAM",
    "memory": "RAM",
    "ssd": "Storage",
    "hdd": "Storage",
    "storage": "Storage",
    "power supply": "PSU",
    "psu": "PSU",
    "casing": "Case",
    "case": "Case",
    "cooler": "Cooling",
    "cooling": "Cooling",
    "monitor": "Monitor",
    "laptop": "Laptop",
}


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


def _infer_brand_from_title(title: str) -> str | None:
    first = (title.strip().split(" ")[0] if title.strip() else "").strip()
    return _clean_brand_name(first, title)


def _clean_brand_name(value: str | None, title: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        # Fallback heuristic: use first token if it looks like a brand word.
        first = (title.strip().split(" ")[0] if title.strip() else "").strip()
        raw = first
    raw = " ".join(raw.split()).strip()
    if not raw:
        return None
    low = raw.lower()
    if low in {"new", "brand", "unknown", "official"}:
        return None
    # Normalize common all-caps vendor names to consistent display.
    known = {
        "msi": "MSI",
        "asus": "ASUS",
        "amd": "AMD",
        "intel": "Intel",
        "nvidia": "NVIDIA",
        "gigabyte": "Gigabyte",
        "acer": "Acer",
        "lenovo": "Lenovo",
        "hp": "HP",
        "dell": "Dell",
    }
    return known.get(low, raw.title())


def _normalize_category(category: str | None, subcategory: str | None, title: str) -> str | None:
    hay = " ".join([(category or ""), (subcategory or ""), (title or "")]).lower()
    for k, v in _STANDARD_CATEGORY_MAP.items():
        if k in hay:
            return v
    return category


def parse_cpu(title: str) -> dict | None:
    t = title.lower()
    if not any(x in t for x in ("intel", "amd", "ryzen", "core i")):
        return None
    out: dict = {}
    if "intel" in t or "core i" in t:
        out["brand"] = "Intel"
    elif "amd" in t or "ryzen" in t:
        out["brand"] = "AMD"
    m = re.search(r"(\d+)\s*core", t)
    if m:
        out["cores"] = int(m.group(1))
    m = re.search(r"(\d+)\s*thread", t)
    if m:
        out["threads"] = int(m.group(1))
    m = re.search(r"\b(am[45]|lga\s?\d{3,4})\b", t, flags=re.I)
    if m:
        out["socket"] = m.group(1).upper().replace(" ", "")
    return out or None


def parse_gpu(title: str) -> dict | None:
    t = title.lower()
    if not any(x in t for x in ("rtx", "gtx", "radeon", "rx ")):
        return None
    out: dict = {}
    if any(x in t for x in ("rtx", "gtx", "nvidia", "geforce")):
        out["brand"] = "NVIDIA"
    elif any(x in t for x in ("radeon", " rx ", "amd")):
        out["brand"] = "AMD"
    m = re.search(r"(\d+)\s*gb", t)
    if m:
        out["vram_gb"] = int(m.group(1))
    return out or None


def parse_ram(title: str) -> dict | None:
    t = title.lower()
    if "ram" not in t and "ddr" not in t:
        return None
    out: dict = {}
    m = re.search(r"\b(ddr[345])\b", t)
    if m:
        out["type"] = m.group(1).upper()
    m = re.search(r"(\d+)\s*gb", t)
    if m:
        out["capacity_gb"] = int(m.group(1))
    m = re.search(r"(\d{3,5})\s*mhz", t)
    if m:
        out["speed_mhz"] = int(m.group(1))
    return out or None


def parse_storage(title: str) -> dict | None:
    t = title.lower()
    if not any(x in t for x in ("ssd", "hdd", "nvme")):
        return None
    out: dict = {}
    if "nvme" in t:
        out["type"] = "NVMe SSD"
    elif "ssd" in t:
        out["type"] = "SSD"
    elif "hdd" in t:
        out["type"] = "HDD"
    m_tb = re.search(r"(\d+)\s*tb", t)
    m_gb = re.search(r"(\d+)\s*gb", t)
    if m_tb:
        out["capacity_gb"] = int(m_tb.group(1)) * 1024
    elif m_gb:
        out["capacity_gb"] = int(m_gb.group(1))
    return out or None


def _extract_specs(title: str, category: str | None) -> dict | None:
    cat = (category or "").lower()
    if cat == "cpu":
        return parse_cpu(title)
    if cat == "gpu":
        return parse_gpu(title)
    if cat == "ram":
        return parse_ram(title)
    if cat == "storage":
        return parse_storage(title)
    # fallback by title heuristics
    for fn in (parse_cpu, parse_gpu, parse_ram, parse_storage):
        res = fn(title)
        if res:
            return res
    return None


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


def _looks_taxonomy_label(text: str) -> bool:
    t = " ".join((text or "").split()).strip()
    if not t or len(t) > 80:
        return False
    # Category labels are usually short and mostly non-numeric.
    if any(ch.isdigit() for ch in t):
        return False
    if len(t.split()) > 6:
        return False
    return True


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
    out["title"] = title[:600].lower()
    out["category"] = _normalize_category(out.get("category"), out.get("subcategory"), title)
    out["price"] = price
    out["review_count"] = review_count
    out["image"] = image
    brand = _clean_brand_name(str(out.get("brand") or ""), title)
    if not brand:
        brand = _infer_brand_from_title(title)
    out["brand"] = brand
    out["url"] = _canonicalize_product_url(url)
    out["specs"] = _extract_specs(out["title"], out.get("category"))
    out["_title_norm"] = _title_norm(title)
    # Data-quality rule: reject rows without required commercial fields.
    if out["price"] is None:
        return None
    return out


def _extract_products_from_html(html: str, base_url: str, site: str, category_name: str, subcategory_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    if site == "techland":
        cards = soup.select(
            "article.products-list__item, article[class*='products-list__item'], article.bg-white.rounded-md.shadow-md"
        )
    elif site == "ryans":
        cards = soup.select("div.category-single-product, div.category-single-product .card.h-100, div.cus-col-2")
    elif site == "skyland":
        cards = soup.select(
            "#content div.main-products-wrapper div.main-products.main-products-style.product-grid.auto-grid > div > div, "
            "div.main-products.product-grid div.product-thumb, "
            "div.product-thumb"
        )
    else:
        cards = soup.select(
            "li.product, div.product, div.product-item, div.product-thumb, div.product-wrapper, div.category-single-product, div.wd-product-wrapper, div.p-item, div.h-full > div.bg-white"
        )
    for c in cards:
        anchors = c.select("a[href]")
        if not anchors:
            continue
        best_a = None
        best_title = ""
        if site == "ryans":
            name_a = c.select_one("h4.product-name a[href], .product-name a[href]")
            if name_a:
                t = name_a.get_text(" ", strip=True)
                if _looks_product_title(t):
                    best_a = name_a
                    best_title = t
        if site == "skyland":
            name_a = c.select_one(".caption .name a[href]")
            if name_a:
                t = name_a.get_text(" ", strip=True)
                if _looks_product_title(t):
                    best_a = name_a
                    best_title = t
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
        try:
            async with CurlSession(impersonate="chrome124", timeout=25) as s:  # type: ignore[misc]
                r = await s.get(url, headers=headers, allow_redirects=True)
                return int(r.status_code), (r.text or "")
        except Exception as e:
            logger.warning("[scrape] curl_fetch_failed site=%s url=%s err=%s -> aiohttp_fallback", site, url, e)

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
    for idx, u in enumerate(candidates, start=1):
        try:
            status, html = await _fetch_text(session, u, site=site, referer=u)
            html_len = len(html or "")
            logger.info(
                "[scrape] homepage_probe site=%s candidate=%s/%s url=%s status=%s body_len=%s",
                site,
                idx,
                len(candidates),
                u,
                status,
                html_len,
            )
            if status >= 400 or not (html or "").strip():
                # Fallback probe: plain request with minimal headers/cookies path.
                try:
                    async with session.get(
                        u,
                        timeout=aiohttp.ClientTimeout(total=20),
                        allow_redirects=True,
                    ) as r:
                        html2 = await r.text()
                        logger.info(
                            "[scrape] homepage_probe_fallback site=%s candidate=%s/%s url=%s status=%s body_len=%s",
                            site,
                            idx,
                            len(candidates),
                            u,
                            r.status,
                            len(html2 or ""),
                        )
                        if r.status < 400 and (html2 or "").strip():
                            status, html = r.status, html2
                except Exception as e2:
                    logger.warning("[scrape] homepage_fallback_failed site=%s url=%s err=%s", site, u, e2)
            if status >= 400 or not (html or "").strip():
                logger.info(
                    "[scrape] homepage_reject site=%s candidate=%s/%s url=%s reason=%s",
                    site,
                    idx,
                    len(candidates),
                    u,
                    "http_error_or_empty",
                )
                continue
            # Don't accept obvious challenge/error pages if we still have candidates.
            low = (html or "").lower()
            # Keep this narrow to avoid false positives from normal page content.
            challenge_markers: list[tuple[str, str]] = [
                ("just a moment", "just_a_moment"),
                ("cf-chl-", "cloudflare_challenge"),
                ("cf-challenge", "cloudflare_challenge"),
                ("challenge-form", "challenge_form"),
                ("/cdn-cgi/challenge-platform/", "cloudflare_challenge"),
            ]
            challenge_hits = [label for marker, label in challenge_markers if marker in low]
            if challenge_hits:
                # Some sites include Cloudflare marker strings in otherwise usable HTML
                # (e.g. a cf-chl- class in a script tag, or /cdn-cgi/ asset reference).
                # For known false-positive sites, probe for a site-specific DOM element
                # that proves the page has real navigable content, not a challenge wall.
                _cf_override_selectors: dict[str, str] = {
                    "ryans": "#navbar_main",
                    "techdiversity": "div.product-wrapper, div.wd-product-wrapper, nav.main-nav, .woocommerce",
                    "techland": "nav.nav-menu, ul.submenu, li.menu-item",
                }
                override_sel = _cf_override_selectors.get(site)
                if override_sel:
                    rsoup = BeautifulSoup(html, "lxml")
                    if rsoup.select_one(override_sel):
                        logger.info(
                            "[scrape] homepage_accept site=%s candidate=%s/%s url=%s status=%s body_len=%s override=content_present",
                            site,
                            idx,
                            len(candidates),
                            u,
                            status,
                            len(html or ""),
                        )
                        return u, html
                logger.info(
                    "[scrape] homepage_reject site=%s candidate=%s/%s url=%s reason=challenge markers=%s",
                    site,
                    idx,
                    len(candidates),
                    u,
                    ",".join(challenge_hits),
                )
                continue
            logger.info(
                "[scrape] homepage_accept site=%s candidate=%s/%s url=%s status=%s body_len=%s",
                site,
                idx,
                len(candidates),
                u,
                status,
                len(html or ""),
            )
            return u, html
        except Exception as e:
            logger.warning(
                "[scrape] homepage_fetch_error site=%s candidate=%s/%s url=%s err=%s",
                site,
                idx,
                len(candidates),
                u,
                e,
            )
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


async def _all_category_urls_for_site(site: str, *, only_urls: set[str] | None = None) -> list[tuple[str, str, str]]:
    async with AsyncSessionLocal() as db:
        if only_urls:
            vals = {f"u{i}": u for i, u in enumerate(sorted(only_urls))}
            placeholders = ", ".join(f":{k}" for k in vals.keys())
            query = (
                """
                SELECT c.url, c.name, COALESCE(p.name, '')
                FROM categories c
                LEFT JOIN categories p ON p.id = c.parent_id
                WHERE c.site = :site
                  AND c.url IN ("""
                + placeholders
                + ")"
            )
            params = {"site": site, **vals}
            rows = await db.execute(text(query), params)
        else:
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
        # Phase 13 data quality guard:
        # reject duplicate URLs within the same scrape batch before touching DB.
        seen_urls: set[str] = set()
        for p in products:
            cleaned = _sanitize_product_row(p)
            if cleaned is None:
                continue
            if cleaned["url"] in seen_urls:
                continue
            seen_urls.add(cleaned["url"])
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
                    INSERT INTO products(site, title, brand, category, subcategory, price, currency, url, image, in_stock, rating, review_count, specs)
                    VALUES (:site, :title, :brand, :category, :subcategory, :price, :currency, :url, :image, :in_stock, :rating, :review_count, :specs)
                    ON CONFLICT(url) DO UPDATE
                    SET price=excluded.price,
                        in_stock=excluded.in_stock,
                        category=COALESCE(products.category, excluded.category),
                        subcategory=COALESCE(products.subcategory, excluded.subcategory),
                        specs=COALESCE(products.specs, excluded.specs),
                        updated_at=CURRENT_TIMESTAMP
                    WHERE products.price IS NOT excluded.price
                       OR products.in_stock IS NOT excluded.in_stock
                    """
                ),
                {
                    k: (json.dumps(v, ensure_ascii=False) if k == "specs" and isinstance(v, (dict, list)) else v)
                    for k, v in cleaned.items()
                    if not str(k).startswith("_")
                },
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


async def _latest_products_updated_at_by_site() -> dict[str, int]:
    out: dict[str, int] = {}
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            text(
                """
                SELECT site, MAX(updated_at)
                FROM products
                WHERE site IS NOT NULL AND site <> ''
                GROUP BY site
                """
            )
        )
        for site, value in rows.fetchall():
            if not site or value is None:
                continue
            if isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue
            else:
                dt = value
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out[str(site).lower()] = int(dt.timestamp())
    return out


def _extract_nav_categories(html: str, homepage: str, site: str) -> list[tuple[str, str, str | None, str | None]]:
    soup = BeautifulSoup(html, "lxml")
    out: list[tuple[str, str, str | None, str | None]] = []
    seen: set[str] = set()

    def _push(name: str, url: str, parent_name: str | None, parent_url: str | None) -> None:
        href = _canonicalize(urljoin(homepage, url))
        if href in seen:
            return
        seen.add(href)
        if site == "ryans" and "/category/" not in urlparse(href).path.lower():
            return
        if _is_blocked_url(href, homepage) or not _looks_category_anchor(name, href):
            return
        out.append((name[:255], href, parent_name[:255] if parent_name else None, _canonicalize(parent_url) if parent_url else None))

    if site == "ryans":
        nav = soup.select_one("#navbar_main")
        if not nav:
            return out
        for item in nav.select("li.has-megamenu"):
            parent_node = item.select_one("button.main-nav-link, a.main-nav-link")
            parent_name = (parent_node.get_text(" ", strip=True) if parent_node else "") or None
            menu = item.select_one(".dropdown-menu.megamenu")
            if not parent_name or not menu:
                continue

            # Keep only category/subcategory links. Exclude deep brand leaf links to prevent
            # 1000+ category explosion from megamenu brand lists.
            anchors = menu.select(
                ".col-megamenu > ul.list-unstyled > li > a[href], "
                "li.hover_drop_down > a.dropdown-toggle[href], "
                "li.hover_drop_down > ul.dropdown-menu2 > li > a[href]"
            )
            if not anchors:
                continue

            parent_href = None
            for a in anchors:
                href = a.get("href", "")
                if "/category/" not in href:
                    continue
                t = a.get_text(" ", strip=True).lower()
                if "all" in t or ("fw-bold" in (a.get("class") or [])):
                    parent_href = href
                    break
            if parent_href is None:
                for a in anchors:
                    href = a.get("href", "")
                    if "/category/" in href:
                        parent_href = href
                        break

            parent_url = None
            if parent_href:
                _push(parent_name, parent_href, None, None)
                parent_url = _canonicalize(urljoin(homepage, parent_href))

            for a in anchors:
                href = a.get("href", "")
                if not href or "/category/" not in href:
                    continue
                child_name = a.get_text(" ", strip=True)
                if not child_name:
                    continue
                cls = set(a.get("class") or [])
                child_l = child_name.lower()
                # Accept only immediate subcategory nodes and "all brands" entries.
                if ("dropdown-toggle" not in cls) and ("all brand" not in child_l) and ("all brands" not in child_l):
                    continue
                _push(child_name, href, parent_name, parent_url)
        return out

    if site == "startech":
        nav = soup.select_one("#main-nav")
        if not nav:
            return out
        top_items = nav.select(":scope > .container > ul.navbar-nav > li.nav-item")
        for top_li in top_items:
            top_a = top_li.select_one(":scope > a[href]")
            if not top_a:
                continue
            top_name = top_a.get_text(" ", strip=True)
            top_href = top_a.get("href", "")
            if not top_name or not top_href:
                continue
            if not _looks_taxonomy_label(top_name):
                continue
            _push(top_name, top_href, None, None)
            top_url = _canonicalize(urljoin(homepage, top_href))
            # Startech mega menu:
            # keep only first-layer category links from drop-menu-1, and parent nodes from nested has-child items.
            for sub_a in top_li.select(
                ":scope > ul.drop-menu-1 > li > a[href], "
                ":scope > div.drop-menu-1 > ul > li > a[href], "
                ":scope > ul.drop-menu-1 > li.has-child > a[href], "
                ":scope > div.drop-menu-1 > ul > li.has-child > a[href]"
            ):
                sub_name = sub_a.get_text(" ", strip=True)
                sub_href = sub_a.get("href", "")
                if not sub_name or not sub_href:
                    continue
                if not _looks_taxonomy_label(sub_name):
                    continue
                href_abs = _canonicalize(urljoin(homepage, sub_href))
                if _is_blocked_url(href_abs, homepage):
                    continue
                # Do not keep deep brand/vendor leaf URLs.
                if len(urlparse(href_abs).path.strip("/").split("/")) > 3:
                    continue
                if "/tool/" in href_abs or sub_name.lower().startswith("show all"):
                    continue
                _push(sub_name, sub_href, top_name, top_url)
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

    if site == "skyland":
        # Skyland top-menu structure from provided selector:
        # #main-menu-2 > ul > li.menu-item...drop-menu
        root = soup.select_one("#main-menu-2")
        if root:
            top_items = root.select(
                ":scope > ul > li.menu-item.main-menu-item.multi-level.dropdown.drop-menu, "
                ":scope > ul > li.menu-item.main-menu-item"
            )
            for parent_li in top_items:
                parent_a = parent_li.select_one(":scope > a[href]")
                if not parent_a:
                    continue
                p_name = ""
                p_name_node = parent_a.select_one("span.links-text")
                if p_name_node:
                    p_name = p_name_node.get_text(" ", strip=True)
                if not p_name:
                    p_name = parent_a.get_text(" ", strip=True)
                p_href = parent_a.get("href", "")
                if not p_name or not p_href:
                    continue
                _push(p_name, p_href, None, None)
                p_url = _canonicalize(urljoin(homepage, p_href))

                # Descendant categories inside dropdown block(s).
                for child_a in parent_li.select(
                    ":scope .dropdown-menu a[href], :scope .j-menu a[href], :scope ul a[href]"
                ):
                    c_name = child_a.get_text(" ", strip=True)
                    c_href = child_a.get("href", "")
                    if not c_name or not c_href:
                        continue
                    _push(c_name, c_href, p_name, p_url)

                # Some Skyland dropdowns are linked via data-target="#collapse-423-*".
                # Resolve those blocks and include all nested dropdown options recursively.
                target_attr = parent_li.select_one(":scope a .open-menu[data-target], :scope .open-menu[data-target]")
                if target_attr:
                    target_id = (target_attr.get("data-target") or "").strip()
                    if target_id.startswith("#"):
                        target_block = soup.select_one(target_id)
                        if target_block:
                            for child_a in target_block.select("ul.j-menu li.menu-item > a[href]"):
                                c_name = child_a.get_text(" ", strip=True)
                                c_href = child_a.get("href", "")
                                if not c_name or not c_href:
                                    continue
                                _push(c_name, c_href, p_name, p_url)
        else:
            # Fallback older Skyland structure:
            # <ul class="j-menu"> <li class="menu-item ... dropdown"> ...
            legacy_root = soup.select_one("ul.j-menu") or soup
            for parent_li in legacy_root.select("li.menu-item.dropdown"):
                parent_a = parent_li.select_one(":scope > a.dropdown-toggle[href], :scope > a[href]")
                if not parent_a:
                    continue
                p_name = parent_a.get_text(" ", strip=True)
                p_href = parent_a.get("href", "")
                if p_name and p_href:
                    _push(p_name, p_href, None, None)
                    p_url = _canonicalize(urljoin(homepage, p_href))
                else:
                    p_url = None

                for child_a in parent_li.select(":scope > .dropdown-menu.j-dropdown ul.j-menu > li.menu-item > a[href]"):
                    c_name = child_a.get_text(" ", strip=True)
                    c_href = child_a.get("href", "")
                    if not c_name or not c_href:
                        continue
                    _push(c_name, c_href, p_name or None, p_url)
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


def _extract_max_page_from_html(html: str) -> int:
    soup = BeautifulSoup(html, "lxml")
    max_page = 1
    # Prefer explicit pagination anchors first.
    for a in soup.select("ul.pagination a[href], .pagination a[href], a[href*='?page=']"):
        href = a.get("href", "")
        for k, v in parse_qsl(urlparse(href).query, keep_blank_values=True):
            if k.lower() == "page" and str(v).isdigit():
                max_page = max(max_page, int(v))
    # Fallback text: "Showing ... (67 Pages)"
    txt = soup.get_text(" ", strip=True)
    m = re.search(r"\((\d+)\s*Pages?\)", txt, flags=re.I)
    if m:
        max_page = max(max_page, int(m.group(1)))
    return max_page


def _extract_skyland_subcategory_candidates(html: str, homepage: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    selectors = [
        ".j-menu a[href]",
        ".dropdown-menu a[href]",
        ".list-group a[href]",
        ".category-list a[href]",
        "aside a[href*='skyland.com.bd']",
    ]
    for sel in selectors:
        for a in soup.select(sel):
            href = _canonicalize(urljoin(homepage, a.get("href", "")))
            if href in seen:
                continue
            seen.add(href)
            name = a.get_text(" ", strip=True)
            if not name or _is_blocked_url(href, homepage):
                continue
            out.append((name[:255], href))
    return out


async def discover_and_scrape_once(sites_to_run: set[str] | None = None) -> dict:
    cycle_t0 = time.perf_counter()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
    }
    result: dict = {
        "generated_at": int(time.time()),
        "sites": {},
        "products_upserted": 0,
        "observability": {
            "products_scraped_total": 0,
            "empty_pages_total": 0,
            "selector_used": {},
            "scrape_duration_seconds": 0.0,
        },
    }
    connector = aiohttp.TCPConnector(limit=40, ttl_dns_cache=300)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        ordered_sites = ["skyland", "ryans", "startech", "techland"]
        site_items = list(SITE_HOMEPAGES.items())
        site_items.sort(key=lambda kv: (0 if kv[0] in ordered_sites else 1, ordered_sites.index(kv[0]) if kv[0] in ordered_sites else 999, kv[0]))
        if sites_to_run is not None:
            wanted = {s.lower() for s in sites_to_run}
            site_items = [it for it in site_items if it[0].lower() in wanted]
        scrape_log(logger, "Scrape Cycle Started", extra=f"sites={len(site_items)}")
        total_sites = len(site_items)
        for idx, (site, homepage_candidates) in enumerate(site_items, start=1):
            site_t0 = time.perf_counter()
            scrape_log(logger, "Scrape Started", site=site, extra=f"{idx}/{total_sites}")
            discovered: set[str] = set()
            products: list[dict] = []
            empty_pages = 0

            resolved = await _fetch_first_available_homepage(session, site, homepage_candidates)
            if resolved is None:
                continue
            homepage, homepage_html = resolved
            # Human-like warmup delay after homepage hit before category crawling.
            await asyncio.sleep(3.0)
            site_sem = asyncio.Semaphore(3 if site in {"ryans", "skyland", "techland"} else 18)

            nav_entries = _extract_nav_categories(homepage_html, homepage, site)
            result["observability"]["selector_used"][site] = {
                "navbar": (
                    "#navbar_main" if site == "ryans"
                    else "#main-menu-2" if site == "skyland"
                    else "#main-nav" if site == "startech"
                    else "nav.nav-menu" if site == "techland"
                    else "generic"
                ),
                "product": (
                    "div.category-single-product" if site == "ryans"
                    else "div.product-thumb/#content .main-products..." if site == "skyland"
                    else "article.products-list__item" if site == "techland"
                    else "generic"
                ),
            }
            if site == "skyland":
                logger.info("[scrape] skyland_nav_entries_initial=%s", len(nav_entries))
            # Some sites render navbar via JS; fallback to whole-document anchor scan.
            if not nav_entries and site not in {"ryans", "startech", "techland"}:
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
            # Skyland: if homepage top-nav is shallow (hover/JS menus not present in source),
            # enrich category list by probing top category pages and collecting subcategory links.
            if site == "skyland":
                base_entries = list(nav_entries)
                if len(base_entries) <= 30:
                    seen_pairs = {(u, p or "") for _, u, _, p in nav_entries}
                    for p_name, p_url, _, _ in base_entries[:24]:
                        try:
                            status, html = await _fetch_text(session, p_url, site=site, referer=homepage)
                        except Exception:
                            continue
                        if status >= 400 or not html:
                            continue
                        for c_name, c_url in _extract_skyland_subcategory_candidates(html, homepage):
                            key = (c_url, p_url)
                            if key in seen_pairs:
                                continue
                            seen_pairs.add(key)
                            nav_entries.append((c_name, c_url, p_name, p_url))
                    logger.info("[scrape] skyland_nav_entries_enriched=%s", len(nav_entries))
            # Site-specific hard fallback when navbar is empty/unreliable.
            if not nav_entries and site in SITE_CATEGORY_FALLBACKS:
                for u in SITE_CATEGORY_FALLBACKS[site]:
                    href = _canonicalize(u)
                    if _is_blocked_url(href, homepage):
                        continue
                    name = urlparse(href).path.strip("/").split("/")[-1].replace("-", " ").title()[:255]
                    nav_entries.append((name, href, None, None))
            if site == "startech" and nav_entries:
                # Final safety gate against mega-menu explosion.
                filtered: list[tuple[str, str, str | None, str | None]] = []
                for n, u, pn, pu in nav_entries:
                    path_parts = [p for p in urlparse(u).path.strip("/").split("/") if p]
                    nlow = (n or "").strip().lower()
                    if not nlow or nlow.startswith("show all"):
                        continue
                    if len(path_parts) > 3:
                        continue
                    if any(x in nlow for x in ("brand", "official", "calculator")):
                        continue
                    filtered.append((n, u, pn, pu))
                nav_entries = filtered
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

            stored_categories = await _all_category_urls_for_site(site, only_urls=discovered)
            max_pages = max(1, int(settings.scrape_max_pages_per_category))
            pages_processed = 0

            async def scrape_category(category_url: str, category_name: str, parent_name: str):
                nonlocal pages_processed, empty_pages
                pages = _listing_pages_for_category(category_url, max_pages=max_pages)
                # First page stays sequential for pagination/type detection.
                if _is_blocked_url(pages[0], homepage):
                    return
                async with site_sem:
                    try:
                        first_status, first_html = await _fetch_text(
                            session,
                            pages[0],
                            site=site,
                            referer=homepage,
                        )
                    except Exception:
                        return
                if first_status == 404 or first_status >= 400 or not first_html:
                    pages_processed += 1
                    return
                if _is_probable_product_detail_page(first_html):
                    return

                allow_pagination = _has_real_listing_pagination(first_html)
                if site == "skyland" and allow_pagination:
                    detected_max = _extract_max_page_from_html(first_html)
                    if detected_max > len(pages):
                        skyland_cap = max(max_pages, 12)
                        pages = _listing_pages_for_category(
                            category_url,
                            max_pages=min(detected_max, skyland_cap),
                        )

                first_rows = _extract_products_from_html(
                    first_html,
                    pages[0],
                    site=site,
                    category_name=parent_name or category_name,
                    subcategory_name=category_name if parent_name else "",
                )
                products.extend(first_rows)
                pages_processed += 1
                if not allow_pagination:
                    return

                # Adaptive concurrent paging:
                # start aggressive (25); if rate-limited, back off to 5.
                page_parallel = 25
                i = 1
                while i < len(pages):
                    batch = [u for u in pages[i : i + page_parallel] if not _is_blocked_url(u, homepage)]
                    if not batch:
                        i += page_parallel
                        continue

                    async def fetch_one(u: str):
                        async with site_sem:
                            try:
                                return u, await _fetch_text(session, u, site=site, referer=category_url)
                            except Exception:
                                return u, (599, "")

                    results = await asyncio.gather(*(fetch_one(u) for u in batch))
                    rate_limited = False
                    for page_url, (status, html) in results:
                        pages_processed += 1
                        if status in {403, 429}:
                            rate_limited = True
                            continue
                        if status == 404:
                            empty_pages += 1
                            continue
                        if status >= 400 or not html:
                            continue
                        rows = _extract_products_from_html(
                            html,
                            page_url,
                            site=site,
                            category_name=parent_name or category_name,
                            subcategory_name=category_name if parent_name else "",
                        )
                        if not rows:
                            empty_pages += 1
                            continue
                        products.extend(rows)

                    if rate_limited and page_parallel > 5:
                        page_parallel = 5
                        logger.warning(
                            "[scrape] %s rate_limited_detected -> reducing page_parallel to %s",
                            site,
                            page_parallel,
                        )
                    if site == "techland" and i < len(pages) - 1:
                        await asyncio.sleep(random.uniform(1.0, 2.5))
                    if site == "skyland" and pages_processed % 25 == 0:
                        elapsed = max(0.001, time.perf_counter() - site_t0)
                        pages_est = max(1, len(stored_categories) * max_pages)
                        ppm = pages_processed / elapsed * 60.0
                        eta_s = max(0.0, (pages_est - pages_processed) / max(0.001, pages_processed / elapsed))
                        scrape_log(
                            logger,
                            "Progress",
                            site=site,
                            extra=f"pages={pages_processed}/{pages_est} products={len(products)} speed={ppm:.1f}p/m eta={int(eta_s)}s",
                        )
                    i += page_parallel

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
            job_results = await asyncio.gather(*jobs, return_exceptions=True)
            failed_jobs = sum(1 for r in job_results if isinstance(r, Exception))
            if failed_jobs:
                logger.warning("[scrape] %s: category_jobs_failed=%s", site, failed_jobs)

            by_link = {}
            for p in products:
                by_link[p["url"]] = p
            upserted = await _upsert_products(list(by_link.values()))
            result["products_upserted"] += upserted
            result["observability"]["products_scraped_total"] += len(by_link)
            result["observability"]["empty_pages_total"] += empty_pages
            result["sites"][site] = {
                "discovered_urls": sorted(discovered),
                "stored_category_urls": [x[0] for x in stored_categories],
                "products": list(by_link.values()),
                "upserted": upserted,
            }
            scrape_log(
                logger,
                "Scrape Done",
                site=site,
                extra=f"products={len(by_link)} upserted={upserted} took={round(time.perf_counter() - site_t0, 1)}s",
            )
            if len(by_link) == 0:
                logger.warning("[scrape] alert_zero_products site=%s", site)

    SNAPSHOT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    scrape_log(
        logger,
        "Scrape Cycle Done",
        extra=f"sites={len(result.get('sites', {}))} upserted={result.get('products_upserted', 0)} took={round(time.perf_counter() - cycle_t0, 1)}s",
    )
    result["observability"]["scrape_duration_seconds"] = round(time.perf_counter() - cycle_t0, 1)
    return result


async def run_full_scrape() -> dict:
    """Single full cycle: navbar category discovery + product upsert."""
    return await discover_and_scrape_once()


async def run_full_scrape_if_stale(max_age_seconds: int = 3600, *, force: bool = False) -> dict:
    now_epoch = int(time.time())
    last_updated = await _latest_products_updated_at_epoch()
    product_count = await _products_row_count()
    site_last = await _latest_products_updated_at_by_site()
    all_sites = [s.lower() for s in SITE_HOMEPAGES.keys()]
    stale_sites: list[str] = []
    fresh_sites: list[str] = []
    site_ages: dict[str, int | None] = {}
    for s in all_sites:
        ts = site_last.get(s)
        if ts is None:
            site_ages[s] = None
            stale_sites.append(s)
            continue
        age = now_epoch - ts
        site_ages[s] = age
        # Guard against clock skew / timezone parse issues producing "future" timestamps.
        if age < 0:
            logger.warning(
                "[scrape] freshness_clock_skew site=%s updated_at_epoch=%s now_epoch=%s age_seconds=%s -> treating_as_stale",
                s,
                ts,
                now_epoch,
                age,
            )
            stale_sites.append(s)
        elif age >= max_age_seconds:
            stale_sites.append(s)
        else:
            fresh_sites.append(s)
    if force:
        logger.info("[scrape] force_run=true -> scraping_now")
    if (not force) and len(stale_sites) == 0 and product_count > 0 and last_updated is not None:
        age = now_epoch - last_updated
        left = max_age_seconds - age
        logger.info(
            "[scrape] skip_fresh_data_all_sites fresh_sites=%s threshold_seconds=%s next_scrape_in_seconds=%s",
            len(fresh_sites),
            max_age_seconds,
            left,
        )
        logger.info(
            "[scrape] skip_notice all sites fresh. Use /api/prewarm/run to force a full cycle."
        )
        return {
            "ran": False,
            "reason": "fresh_data_all_sites",
            "last_updated_epoch": last_updated,
            "products_upserted": 0,
            "sites": {},
            "fresh_sites": fresh_sites,
            "stale_sites": stale_sites,
        }
    logger.info(
        "[scrape] stale_or_empty_data last_updated_epoch=%s product_count=%s threshold_seconds=%s fresh_sites=%s stale_sites=%s -> scraping_now",
        last_updated,
        product_count,
        max_age_seconds,
        len(fresh_sites),
        len(stale_sites),
    )
    if fresh_sites:
        detail = ", ".join(f"{s}:{site_ages.get(s)}s" for s in fresh_sites)
        logger.info("[scrape] fresh_site_ages %s", detail)
    if stale_sites:
        detail = ", ".join(f"{s}:{site_ages.get(s)}s" for s in stale_sites if site_ages.get(s) is not None)
        if detail:
            logger.info("[scrape] stale_site_ages %s", detail)
    data = await discover_and_scrape_once(None if force else set(stale_sites))
    data["ran"] = True
    data["fresh_sites"] = fresh_sites
    data["stale_sites"] = stale_sites if not force else all_sites
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

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "prewarm_snapshot.json"

SITE_CATEGORY_SEEDS: dict[str, list[str]] = {
    "startech": [
        "https://www.startech.com.bd/component/processor",
        "https://www.startech.com.bd/component/cooling-fan",
        "https://www.startech.com.bd/component/motherboard",
        "https://www.startech.com.bd/component/graphics-card",
        "https://www.startech.com.bd/component/ram",
        "https://www.startech.com.bd/component/ssd-msata",
        "https://www.startech.com.bd/component/hard-disk-drive",
        "https://www.startech.com.bd/component/power-supply",
        "https://www.startech.com.bd/component/casing",
    ],
    "skyland": [
        "https://www.skyland.com.bd/processor",
        "https://www.skyland.com.bd/cpu-cooler",
        "https://www.skyland.com.bd/motherboard",
        "https://www.skyland.com.bd/graphics-card",
        "https://www.skyland.com.bd/desktop-ram",
        "https://www.skyland.com.bd/ssd",
        "https://www.skyland.com.bd/power-supply",
        "https://www.skyland.com.bd/casing",
    ],
    "techland": [
        "https://www.techlandbd.com/pc-components/processor",
        "https://www.techlandbd.com/pc-components/cpu-cooler",
        "https://www.techlandbd.com/pc-components/motherboard",
        "https://www.techlandbd.com/pc-components/graphics-card",
        "https://www.techlandbd.com/pc-components/computer-ram",
        "https://www.techlandbd.com/pc-components/solid-state-drive",
        "https://www.techlandbd.com/pc-components/power-supply",
        "https://www.techlandbd.com/pc-components/computer-casing",
    ],
    "ryans": [
        "https://www.ryans.com/category/desktop-component-processor",
        "https://www.ryans.com/category/desktop-component-cpu-cooler",
        "https://www.ryans.com/category/desktop-component-motherboard",
        "https://www.ryans.com/category/desktop-component-graphics-card",
        "https://www.ryans.com/category/desktop-component-desktop-ram",
        "https://www.ryans.com/category/desktop-component-ssd",
        "https://www.ryans.com/category/desktop-component-power-supply",
        "https://www.ryans.com/category/desktop-component-casing",
    ],
    "potaka": [
        "https://potakait.com/components/processor",
        "https://potakait.com/components/cpu-cooling-fan",
        "https://potakait.com/components/motherboard",
        "https://potakait.com/components/graphics-card",
        "https://potakait.com/components/ram-desktop",
        "https://potakait.com/components/ssd",
        "https://potakait.com/components/power-supply",
        "https://potakait.com/components/casing",
    ],
    "techdiversity": [
        "https://techdiversitybd.com/product-category/pc-components/processor",
        "https://techdiversitybd.com/product-category/pc-components/motherboard",
        "https://techdiversitybd.com/product-category/pc-components/graphics-card",
        "https://techdiversitybd.com/product-category/pc-components/ram",
        "https://techdiversitybd.com/product-category/pc-components/casing",
    ],
    "vibe": [
        "https://vibegaming.com.bd/product-category/component/processor",
        "https://vibegaming.com.bd/product-category/component/motherboard",
        "https://vibegaming.com.bd/product-category/component/graphics-card",
        "https://vibegaming.com.bd/product-category/component/ram-desktop",
        "https://vibegaming.com.bd/product-category/component/ssd",
        "https://vibegaming.com.bd/product-category/component/power-supply",
    ],
    "blisstronics": [
        "https://blisstronics.com/product-category/pc-components/processor",
        "https://blisstronics.com/product-category/pc-components/motherboard",
        "https://blisstronics.com/product-category/pc-components/graphics-card",
        "https://blisstronics.com/product-category/pc-components/ram",
        "https://blisstronics.com/product-category/pc-components/power-supply",
    ],
}


def _same_host(a: str, b: str) -> bool:
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()


def _looks_category_path(path: str) -> bool:
    p = path.lower()
    hints = (
        "component",
        "pc-components",
        "product-category",
        "processor",
        "motherboard",
        "graphics-card",
        "ram",
        "ssd",
        "hard-disk",
        "power-supply",
        "casing",
        "cpu-cooler",
    )
    return any(h in p for h in hints)


def _extract_products_from_html(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    cards = soup.select(
        "div.p-item, div.product-thumb, div.category-single-product, div.product-item, div.product-wrapper, div.wd-product-wrapper, div.h-full > div.bg-white"
    )
    for c in cards:
        a = c.select_one("a[href]")
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        if len(title) < 3:
            continue
        href = urljoin(base_url, a.get("href", ""))
        txt = c.get_text(" ", strip=True)
        m = re.search(r"(?:৳|Tk\\.?\\s*)\\s*([\\d,]+(?:\\.\\d+)?)", txt, flags=re.I)
        price = float(m.group(1).replace(",", "")) if m else 0.0
        out.append({"title": title, "price": price, "link": href})
    return out


async def _fetch_text(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
        r.raise_for_status()
        return await r.text()


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
    result: dict = {"generated_at": int(time.time()), "sites": {}}
    connector = aiohttp.TCPConnector(limit=40, ttl_dns_cache=300)
    sem = asyncio.Semaphore(20)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        for site, seeds in SITE_CATEGORY_SEEDS.items():
            site_t0 = time.perf_counter()
            logger.info("[scrape] site_start site=%s seed_count=%s", site, len(seeds))
            discovered: set[str] = set(seeds)
            products: list[dict] = []

            async def process_seed(seed_url: str):
                async with sem:
                    try:
                        html = await _fetch_text(session, seed_url)
                    except Exception:
                        return
                soup = BeautifulSoup(html, "lxml")
                for a in soup.select("a[href]"):
                    href = urljoin(seed_url, a.get("href", ""))
                    if not _same_host(href, seed_url):
                        continue
                    if _looks_category_path(urlparse(href).path):
                        discovered.add(href.split("#")[0].rstrip("/"))
                products.extend(_extract_products_from_html(html, seed_url))

            await asyncio.gather(*(process_seed(u) for u in seeds))

            # scrape discovered URLs once (page 1 only) for hourly bot speed
            async def process_discovered(url: str):
                async with sem:
                    try:
                        html = await _fetch_text(session, url)
                    except Exception:
                        return
                products.extend(_extract_products_from_html(html, url))

            await asyncio.gather(*(process_discovered(u) for u in sorted(discovered)))

            # de-duplicate products by link
            by_link = {}
            for p in products:
                by_link[p["link"]] = p
            result["sites"][site] = {
                "discovered_urls": sorted(discovered),
                "products": list(by_link.values()),
            }
            logger.info(
                "[scrape] site_end site=%s discovered_urls=%s products=%s elapsed_ms=%s",
                site,
                len(discovered),
                len(by_link),
                int((time.perf_counter() - site_t0) * 1000),
            )

    SNAPSHOT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "[scrape] cycle_end snapshot_path=%s site_count=%s elapsed_ms=%s",
        str(SNAPSHOT_PATH),
        len(result.get("sites", {})),
        int((time.perf_counter() - cycle_t0) * 1000),
    )
    return result


async def run_prewarm_forever(interval_seconds: int = 3600, *, run_immediately: bool = True) -> None:
    if not run_immediately:
        await asyncio.sleep(max(300, interval_seconds))
    while True:
        try:
            await discover_and_scrape_once()
        except Exception as e:
            logger.warning("prewarm cycle failed: %s", e)
        await asyncio.sleep(max(300, interval_seconds))

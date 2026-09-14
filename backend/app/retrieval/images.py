"""Product photo pipeline, run as part of the catalog sync.

The seed catalog hot-links photos from ~30 third-party hosts at full size —
over 12 MB for 50 products, several files over 1 MB, a few behind hotlink
protection or broken TLS. Serving those directly makes the storefront slow
and fragile. So the sync fetches each photo once, shrinks it to a 640px WebP
(~13x smaller), and publishes it to a public Supabase Storage bucket. The
row written to `catalog_products` then carries the Storage URL, and the
storefront loads every image from a single CDN origin it already trusts.

`catalog.json` itself keeps the original URLs: it is the record of *where the
photo came from*, and re-running the sync is always safe and idempotent.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import ssl
import urllib.error
import urllib.request

from app.clients import supabase_client

logger = logging.getLogger(__name__)

BUCKET = "product-images"
MAX_WIDTH = 640
QUALITY = 82
_CONCURRENCY = 6

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
}


def _download(url: str) -> bytes:
    # A Referer matching the host gets past most hotlink protection.
    headers = {**_HEADERS, "Referer": f"https://{url.split('/')[2]}/"}
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return r.read()
    except urllib.error.URLError as e:
        # urllib wraps certificate failures as URLError(reason=SSLError). A couple of
        # catalog hosts have broken certificates; the image bytes themselves are fine.
        if not isinstance(e.reason, ssl.SSLError):
            raise
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return r.read()


def _to_webp(raw: bytes) -> bytes:
    from PIL import Image, ImageOps

    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    if im.mode not in ("RGB", "RGBA"):
        keep_alpha = im.mode in ("P", "LA") or "transparency" in im.info
        im = im.convert("RGBA" if keep_alpha else "RGB")
    if im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "WEBP", quality=QUALITY, method=6)
    return out.getvalue()


async def ensure_bucket() -> None:
    """Create the public bucket on first run; a no-op afterwards."""
    storage = supabase_client().storage
    existing = {b.name for b in await storage.list_buckets()}
    if BUCKET not in existing:
        await storage.create_bucket(BUCKET, options={"public": True, "allowed_mime_types": ["image/webp"]})
        logger.info("images: created public storage bucket '%s'", BUCKET)


async def publish_product_image(product_id: str, source_url: str) -> str:
    """Fetch, compress, upload. Returns the public CDN URL, versioned by content
    hash so browsers can cache it for a year yet still pick up a changed photo."""
    raw = await asyncio.to_thread(_download, source_url)
    webp = await asyncio.to_thread(_to_webp, raw)
    path = f"{product_id}.webp"
    bucket = supabase_client().storage.from_(BUCKET)
    await bucket.upload(
        path, webp,
        file_options={"content-type": "image/webp", "cache-control": "31536000", "upsert": "true"},
    )
    digest = hashlib.sha1(webp).hexdigest()[:10]
    return f"{await bucket.get_public_url(path)}?v={digest}"


async def optimize_catalog_images(rows: list[dict]) -> tuple[list[dict], int, int]:
    """Rewrite each row's `image_url` to its published WebP. A photo that can't be
    fetched keeps its original URL and is reported — one bad host never blocks
    the sync. Returns (rows, published_count, failed_count)."""
    await ensure_bucket()
    sem = asyncio.Semaphore(_CONCURRENCY)
    published = failed = 0

    async def one(row: dict) -> dict:
        nonlocal published, failed
        url = row.get("image_url") or ""
        if not url or "/storage/v1/object/public/" in url:
            return row  # nothing to fetch, or already ours
        async with sem:
            try:
                new_url = await publish_product_image(row["id"], url)
            except Exception as e:  # noqa: BLE001
                failed += 1
                logger.warning("images: %s kept original URL (%s: %s)", row["id"], type(e).__name__, str(e)[:80])
                return row
        published += 1
        return {**row, "image_url": new_url}

    out = await asyncio.gather(*(one(r) for r in rows))
    return list(out), published, failed

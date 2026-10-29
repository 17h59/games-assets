#!/usr/bin/env python3
"""
Spriters Resource Scraper
=========================
Fast, robust scraper for downloading sprite sheets and assets from https://www.spriters-resource.com/

Features:
- Automatic Cloudflare bypass with nodriver and xvfb (cached session, transparent renewal).
- High-speed concurrent downloads using curl_cffi.
- Supports Game pages (downloads all or filtered sections) and Asset subpages.
- Organizes downloads by Game / Section / AssetName.ext.
- Generates a metadata.json index.
"""

import os
import sys
import re
import json
import time
import shutil
import logging
import argparse
import subprocess
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple, Dict, Any

from bs4 import BeautifulSoup
from curl_cffi import requests
from tqdm import tqdm

BASE_URL = "https://www.spriters-resource.com"
SESSION_CACHE_FILE = os.path.expanduser("~/.cache/spriters_scraper/session.json")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("spriters_scraper")


def sanitize_filename(name: str) -> str:
    """Sanitize string for filesystem paths."""
    # Replace illegal filesystem chars
    s = re.sub(r'[\\/*?:"<>|]', "_", name)
    # Collapse whitespace and strip
    s = re.sub(r'\s+', ' ', s).strip()
    return s or "unnamed"


@dataclass
class SpriterAsset:
    asset_id: str
    title: str
    section: str
    page_url: str
    icon_url: str
    media_url: str
    game_title: str = ""
    console_title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CloudflareSessionManager:
    """Manages Cloudflare clearance tokens and curl_cffi sessions."""

    def __init__(self, cache_file: str = SESSION_CACHE_FILE):
        self.cache_file = cache_file
        self.user_agent: Optional[str] = None
        self.cookies: Dict[str, str] = {}
        self.session: Optional[requests.Session] = None
        self.load_cache()

    def load_cache(self) -> bool:
        if not os.path.exists(self.cache_file):
            return False
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.user_agent = data.get("user_agent")
                self.cookies = data.get("cookies", {})
                timestamp = data.get("timestamp", 0)
                # Cloudflare cf_clearance usually lasts between 2h to 24h
                if time.time() - timestamp > 3600 * 12:
                    logger.debug("Cached session older than 12 hours, may require refresh.")
                return bool(self.user_agent and self.cookies.get("cf_clearance"))
        except Exception as e:
            logger.debug(f"Failed to load cached session: {e}")
            return False

    def save_cache(self):
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump({
                    "user_agent": self.user_agent,
                    "cookies": self.cookies,
                    "timestamp": time.time()
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save session cache: {e}")

    def solve_challenge_with_browser(self, target_url: str = BASE_URL) -> bool:
        """Launches nodriver to solve Cloudflare challenge and retrieve cookies."""
        logger.info("Resolving Cloudflare challenge with browser...")
        
        # Helper python script to run inside or outside xvfb
        solver_code = f"""
import asyncio
import nodriver as uc
import json

async def main():
    browser = await uc.start(headless=False)
    page = await browser.get('{target_url}')
    ua = await page.evaluate('navigator.userAgent')
    cookies = {{}}
    for _ in range(25):
        await asyncio.sleep(1)
        raw_cookies = await browser.cookies.get_all()
        cookies = {{c.name: c.value for c in raw_cookies}}
        if 'cf_clearance' in cookies:
            break
    browser.stop()
    print(json.dumps({{'user_agent': ua, 'cookies': cookies}}))

asyncio.run(main())
"""
        cmd = [sys.executable, "-c", solver_code]
        # Use xvfb-run if available and headless is preferred or no display
        has_xvfb = shutil.which("xvfb-run") is not None
        if has_xvfb and not os.environ.get("SP_SHOW_BROWSER"):
            run_cmd = ["xvfb-run", "-a"] + cmd
        else:
            run_cmd = cmd

        try:
            proc = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=45,
                check=True
            )
            # Find JSON in output
            lines = proc.stdout.strip().splitlines()
            for line in reversed(lines):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    data = json.loads(line)
                    self.user_agent = data.get("user_agent")
                    self.cookies = data.get("cookies", {})
                    if "cf_clearance" in self.cookies:
                        logger.info("Cloudflare challenge successfully solved!")
                        self.save_cache()
                        self._init_session()
                        return True
            logger.error(f"Challenge output did not contain clearance cookie: {proc.stdout}")
            return False
        except Exception as e:
            logger.error(f"Error solving challenge: {e}")
            return False

    def _init_session(self):
        self.session = requests.Session(impersonate="chrome")
        if self.user_agent:
            self.session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
                "Referer": BASE_URL + "/",
            })
        if self.cookies:
            self.session.cookies.update(self.cookies)

    def get_session(self, force_refresh: bool = False, test_url: str = BASE_URL) -> requests.Session:
        if force_refresh or not self.session:
            if not force_refresh and self.cookies.get("cf_clearance"):
                self._init_session()
                # Test validity
                try:
                    res = self.session.get(test_url, timeout=10)
                    if res.status_code == 200:
                        return self.session
                    elif res.status_code == 403:
                        logger.info("Session expired (403), refreshing...")
                except Exception as e:
                    logger.debug(f"Session test exception: {e}")

            # Must solve challenge
            if not self.solve_challenge_with_browser(test_url):
                raise RuntimeError("Failed to bypass Cloudflare protection.")
        
        return self.session


class SpritersScraper:
    """Scraper implementation for Spriters Resource."""

    def __init__(self, session_manager: Optional[CloudflareSessionManager] = None):
        self.sm = session_manager or CloudflareSessionManager()
        self.session = self.sm.get_session()

    def _fetch_html(self, url: str) -> str:
        """Fetches page HTML with automatic retry if session expires."""
        for attempt in range(2):
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 403:
                logger.warning(f"Got 403 on {url}, renewing session...")
                self.session = self.sm.get_session(force_refresh=True, test_url=url)
            else:
                resp.raise_for_status()
        raise RuntimeError(f"Unable to fetch {url} after session renewal.")

    def parse_game_page(self, game_url: str) -> Tuple[Dict[str, str], List[SpriterAsset]]:
        """
        Parses a game page (e.g. /game_boy_advance/pokemonemerald/)
        Returns:
            meta: {'game': ..., 'console': ...}
            assets: list of SpriterAsset
        """
        if not game_url.startswith("http"):
            game_url = urljoin(BASE_URL, game_url)

        html = self._fetch_html(game_url)
        soup = BeautifulSoup(html, "html.parser")

        # Parse Game and Console Title from <title> or <h1>
        game_title = "Unknown Game"
        console_title = "Unknown Console"
        
        h1 = soup.find("h1")
        if h1:
            game_title = h1.text.strip()
            
        # Parse from title tag: "Game Title - Console - The Spriters Resource"
        if soup.title and soup.title.string:
            parts = [p.strip() for p in soup.title.string.split(" - ")]
            if len(parts) >= 3:
                game_title = parts[0]
                console_title = parts[1]

        asset_display = soup.find(id="asset-display")
        if not asset_display:
            # Fallback if id has changed or differs
            asset_display = soup.find(id="content")

        assets: List[SpriterAsset] = []
        if not asset_display:
            logger.warning(f"No asset display found on {game_url}")
            return {"game": game_title, "console": console_title}, assets

        # The structure is pairs of:
        # <div class="section ...">Section Name</div>
        # <div class="icondisplay"> ... <a class="iconlink" ...> ... </div>
        current_section = "General"

        for elem in asset_display.find_all(["div"]):
            classes = elem.get("class", [])
            
            # Check if this element is a section header
            if "section" in classes and "end-border" in classes:
                # Clean section title (remove material icons text like 'arrow_drop_down' and count '[10]')
                raw_text = elem.text.strip()
                cleaned = re.sub(r"arrow_drop_down", "", raw_text)
                cleaned = re.sub(r"\[\d+\]", "", cleaned).strip()
                if cleaned:
                    current_section = cleaned
                continue

            # Check if this element contains asset cards
            if "icondisplay" in classes:
                cards = elem.find_all("a", class_="iconlink")
                for card in cards:
                    href = card.get("href", "")
                    if not href:
                        continue
                    
                    # Extract asset ID from href /.../asset/<id>/
                    id_match = re.search(r"/asset/(\d+)/?", href)
                    asset_id = id_match.group(1) if id_match else ""
                    
                    # Asset Title
                    header_el = card.find(class_="iconheader")
                    title = header_el.get("title") or header_el.text.strip() if header_el else f"Asset_{asset_id}"
                    
                    # Icon image
                    img_el = card.find("img")
                    icon_src = img_el.get("src", "") if img_el else ""
                    icon_url = urljoin(BASE_URL, icon_src)
                    
                    # Direct media URL derived from icon:
                    # /media/asset_icons/<folder>/<id>.png -> /media/assets/<folder>/<id>.png
                    media_url = ""
                    if "/media/asset_icons/" in icon_src:
                        clean_src = icon_src.split("?")[0]
                        media_path = clean_src.replace("/media/asset_icons/", "/media/assets/")
                        media_url = urljoin(BASE_URL, media_path)

                    page_url = urljoin(BASE_URL, href)
                    assets.append(SpriterAsset(
                        asset_id=asset_id,
                        title=title,
                        section=current_section,
                        page_url=page_url,
                        icon_url=icon_url,
                        media_url=media_url,
                        game_title=game_title,
                        console_title=console_title
                    ))

        return {"game": game_title, "console": console_title}, assets

    def parse_asset_page(self, asset_url: str) -> SpriterAsset:
        """Parses an asset subpage directly (e.g. /game_boy_advance/pokemonemerald/asset/523725/)."""
        if not asset_url.startswith("http"):
            asset_url = urljoin(BASE_URL, asset_url)

        html = self._fetch_html(asset_url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract title and game from title tag
        # Title format: "Asset Title - Game Title - Console - The Spriters Resource"
        title = "Unknown Asset"
        game_title = "Unknown Game"
        console_title = "Unknown Console"
        if soup.title and soup.title.string:
            parts = [p.strip() for p in soup.title.string.split(" - ")]
            if len(parts) >= 3:
                title = parts[0]
                game_title = parts[1]
                console_title = parts[2]

        id_match = re.search(r"/asset/(\d+)/?", asset_url)
        asset_id = id_match.group(1) if id_match else ""

        # Find download link: <a href="/media/assets/..." ...>download</a>
        media_url = ""
        download_a = soup.find("a", string=lambda s: s and "download" in s.lower())
        if download_a and download_a.get("href"):
            media_url = urljoin(BASE_URL, download_a["href"].split("?")[0])
        else:
            # Fallback: look for <img> with /media/assets/
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if "/media/assets/" in src:
                    media_url = urljoin(BASE_URL, src.split("?")[0])
                    break

        # Icon URL
        icon_meta = soup.find("meta", property="og:image")
        icon_url = urljoin(BASE_URL, icon_meta["content"]) if icon_meta and icon_meta.get("content") else ""

        return SpriterAsset(
            asset_id=asset_id,
            title=title,
            section="Assets",
            page_url=asset_url,
            icon_url=icon_url,
            media_url=media_url,
            game_title=game_title,
            console_title=console_title
        )

    def resolve_asset_media_url(self, asset: SpriterAsset) -> str:
        """If media_url is missing or failed, visits subpage to get exact download URL."""
        if asset.media_url:
            return asset.media_url
        detailed = self.parse_asset_page(asset.page_url)
        asset.media_url = detailed.media_url
        return asset.media_url

    def download_asset(
        self,
        asset: SpriterAsset,
        base_dir: str,
        overwrite: bool = False,
        use_deep_fallback: bool = True
    ) -> Tuple[bool, str]:
        """
        Downloads a single asset to disk.
        Returns: (success: bool, filepath_or_error: str)
        """
        # Determine directory structure: base_dir / Game / Section / Asset.ext
        game_dir = sanitize_filename(asset.game_title or "spriters")
        section_dir = sanitize_filename(asset.section or "Assets")
        target_dir = os.path.join(base_dir, game_dir, section_dir)
        os.makedirs(target_dir, exist_ok=True)

        # File extension
        url = asset.media_url
        if not url:
            if use_deep_fallback:
                url = self.resolve_asset_media_url(asset)
            if not url:
                return False, f"No media URL found for asset {asset.asset_id}"

        clean_url = url.split("?")[0]
        ext = os.path.splitext(clean_url)[1] or ".png"
        filename = f"{sanitize_filename(asset.title)}_{asset.asset_id}{ext}"
        filepath = os.path.join(target_dir, filename)

        if not overwrite and os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return True, f"Skipped (already exists): {filepath}"

        # Download file
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                return True, filepath
            elif resp.status_code == 404 and use_deep_fallback:
                # Try resolving via subpage in case the extension or path differs (e.g. .zip / .gif)
                detailed_url = self.resolve_asset_media_url(asset)
                if detailed_url and detailed_url != url:
                    resp = self.session.get(detailed_url, timeout=20)
                    if resp.status_code == 200:
                        new_ext = os.path.splitext(detailed_url.split("?")[0])[1] or ext
                        filepath = os.path.join(target_dir, f"{sanitize_filename(asset.title)}_{asset.asset_id}{new_ext}")
                        with open(filepath, "wb") as f:
                            f.write(resp.content)
                        return True, filepath
            elif resp.status_code == 403:
                # Session expired during download
                self.session = self.sm.get_session(force_refresh=True, test_url=url)
                resp = self.session.get(url, timeout=20)
                if resp.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    return True, filepath

            return False, f"HTTP {resp.status_code} on {url}"
        except Exception as e:
            return False, str(e)


def run_scraper(
    target_url: str,
    output_dir: str = "./downloads",
    concurrency: int = 4,
    section_filter: Optional[str] = None,
    overwrite: bool = False,
    list_only: bool = False,
    deep_mode: bool = False
):
    """Main execution orchestrator."""
    sm = CloudflareSessionManager()
    scraper = SpritersScraper(sm)

    parsed_url = urlparse(target_url)
    is_asset_page = "/asset/" in parsed_url.path and bool(re.search(r"/asset/\d+", parsed_url.path))

    if is_asset_page:
        logger.info(f"Target is a single asset: {target_url}")
        asset = scraper.parse_asset_page(target_url)
        assets = [asset]
        meta = {"game": asset.game_title, "console": asset.console_title}
    else:
        logger.info(f"Target is a game / section page: {target_url}")
        meta, assets = scraper.parse_game_page(target_url)

    logger.info(f"Game: {meta.get('game', 'Unknown')} ({meta.get('console', 'Unknown')})")
    logger.info(f"Found {len(assets)} total assets.")

    # Filter by section if requested
    if section_filter:
        regex = re.compile(section_filter, re.IGNORECASE)
        assets = [a for a in assets if regex.search(a.section)]
        logger.info(f"Filtered to {len(assets)} assets in section matching '{section_filter}'.")

    if not assets:
        logger.warning("No assets to process.")
        return

    # Group by section for report
    sections: Dict[str, List[SpriterAsset]] = {}
    for a in assets:
        sections.setdefault(a.section, []).append(a)

    print("\n" + "=" * 60)
    print(f"🎮  GAME: {meta.get('game')} [{meta.get('console')}]")
    print(f"📦  TOTAL ASSETS: {len(assets)}")
    print("📁  SECTIONS:")
    for sect, items in sections.items():
        print(f"   • {sect}: {len(items)} assets")
    print("=" * 60 + "\n")

    if list_only:
        print("Assets listing:")
        for a in assets:
            print(f" - [{a.section}] {a.title} (ID: {a.asset_id}) -> {a.media_url}")
        return

    # If deep mode requested, pre-resolve all media URLs
    if deep_mode:
        logger.info("Deep mode enabled: resolving exact media URLs from asset subpages...")
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(scraper.resolve_asset_media_url, a) for a in assets]
            for _ in tqdm(as_completed(futures), total=len(futures), desc="Parsing subpages"):
                pass

    # Save metadata.json
    game_dir = os.path.join(output_dir, sanitize_filename(meta.get("game") or "spriters"))
    os.makedirs(game_dir, exist_ok=True)
    metadata_file = os.path.join(game_dir, "metadata.json")
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump({
            "game": meta.get("game"),
            "console": meta.get("console"),
            "source_url": target_url,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_assets": len(assets),
            "assets": [a.to_dict() for a in assets]
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"Metadata saved to {metadata_file}")

    # Concurrent Download
    logger.info(f"Starting download of {len(assets)} assets with {concurrency} workers...")
    start_time = time.time()
    downloaded = 0
    skipped = 0
    errors = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_asset = {
            executor.submit(scraper.download_asset, a, output_dir, overwrite, not deep_mode): a
            for a in assets
        }
        
        with tqdm(total=len(assets), desc="Downloading Assets", unit="file") as pbar:
            for future in as_completed(future_to_asset):
                asset = future_to_asset[future]
                try:
                    ok, msg = future.result()
                    if ok:
                        if "Skipped" in msg:
                            skipped += 1
                        else:
                            downloaded += 1
                    else:
                        errors.append((asset, msg))
                except Exception as e:
                    errors.append((asset, str(e)))
                pbar.update(1)

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("🎉  DOWNLOAD COMPLETED")
    print(f"⏱️   Elapsed time: {elapsed:.2f}s (avg {(elapsed/len(assets) if assets else 0):.2f}s/file)")
    print(f"✅  Downloaded: {downloaded}")
    print(f"⏩  Skipped (existing): {skipped}")
    print(f"❌  Errors: {len(errors)}")
    if errors:
        print("\nErrors summary (first 5):")
        for asset, err in errors[:5]:
            print(f"  - [{asset.asset_id}] {asset.title}: {err}")
    print(f"📂  Saved to: {os.path.abspath(game_dir)}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Fast downloader for The Spriters Resource",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Download all assets from Pokemon Emerald:
  python tools/spriters_scraper.py https://www.spriters-resource.com/game_boy_advance/pokemonemerald/

  # Download only Pokemon characters:
  python tools/spriters_scraper.py https://www.spriters-resource.com/game_boy_advance/pokemonemerald/ --section "Playable Characters"

  # Download a single asset:
  python tools/spriters_scraper.py https://www.spriters-resource.com/game_boy_advance/pokemonemerald/asset/523725/

  # List assets without downloading:
  python tools/spriters_scraper.py https://www.spriters-resource.com/game_boy_advance/pokemonemerald/ --list
"""
    )
    parser.add_argument("url", help="URL of the game or asset on spriters-resource.com")
    parser.add_argument("-o", "--output", default="./downloads", help="Destination directory (default: ./downloads)")
    parser.add_argument("-c", "--concurrency", type=int, default=4, help="Concurrent download threads (default: 4)")
    parser.add_argument("-s", "--section", help="Filter by section regex/name (e.g. 'Playable Characters', 'Gyms')")
    parser.add_argument("-f", "--force", action="store_true", help="Force re-download even if files already exist")
    parser.add_argument("-l", "--list", action="store_true", help="List assets and sections without downloading")
    parser.add_argument("--deep", action="store_true", help="Visit each asset subpage to resolve download links directly")

    args = parser.parse_args()

    run_scraper(
        target_url=args.url,
        output_dir=args.output,
        concurrency=args.concurrency,
        section_filter=args.section,
        overwrite=args.force,
        list_only=args.list,
        deep_mode=args.deep
    )


if __name__ == "__main__":
    main()

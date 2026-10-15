"""Download/index the supplied V5 Automation mirror without executing its scripts.

The index covers all TOC links. --pages downloads all referenced HTML pages;
--match restricts page downloads, not the index. Downloads are resumable.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import time
import subprocess
import re
from urllib.parse import urljoin, urlsplit, urldefrag

BASE = "https://catiadesign.org/_doc/V5Automation/"
ROOT = Path(__file__).resolve().parents[1] / ".local" / "v5-reference"


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.text, self.current = [], [], None
        self.hidden = 0
        self.in_script = False
        self.script_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self.hidden += 1
        if tag == "script":
            self.in_script = True
            self.script_text = []
        if tag == "a" and attrs.get("href"):
            self.current = [attrs["href"], attrs.get("title", ""), []]

    def handle_data(self, data):
        if self.in_script:
            self.script_text.append(data)
        if not self.hidden and data.strip():
            self.text.append(data.strip())
            if self.current:
                self.current[2].append(data.strip())

    def handle_endtag(self, tag):
        if tag == "script":
            # CAA renders signature types via activateLink('Reference','Reference').
            # Extract only this literal label; never evaluate JavaScript.
            self.text.extend(re.findall(r"activateLink\(\s*'([A-Za-z_][A-Za-z_0-9]*)'\s*,\s*'[A-Za-z_][A-Za-z_0-9]*'\s*\)", "".join(self.script_text)))
            self.in_script = False
            self.script_text = []
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if tag == "a" and self.current:
            href, title, text = self.current
            self.links.append((href, title or " ".join(text)))
            self.current = None


def fetch(url):
    # System curl uses the OS CA store. TLS verification stays enabled; no -k.
    # No -L: redirects cannot escape the explicitly scoped documentation tree.
    if not url.startswith(BASE):
        raise ValueError("URL outside reference tree")
    data = subprocess.check_output(["curl", "--silent", "--show-error", "--fail",
        "--max-time", "30", "--max-filesize", "12000000", "--retry", "1", url], stderr=subprocess.PIPE)
    return data, data.decode("utf-8-sig", errors="replace")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", action="store_true")
    parser.add_argument("--match", default="")
    parser.add_argument("--refresh", action="store_true", help="Replace matched cached pages using current parser")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    data, html = fetch(BASE + "V5Automation.htm")
    (ROOT / "V5Automation.htm").write_bytes(data)
    page = Page()
    page.feed(html)
    entries, seen = [], set()
    for href, title in page.links:
        url = urljoin(BASE, href)
        parts = urlsplit(url)
        if not url.startswith(BASE) or not parts.path.lower().endswith((".htm", ".html")) or url in seen:
            continue
        seen.add(url)
        entries.append({"title": title, "url": url})
    manifest = {"source": BASE, "source_kind": "third-party mirror of CAA V5 Automation documentation",
                "fetched_at_unix": time.time(), "toc_sha256": hashlib.sha256(data).hexdigest(),
                "entries": entries}
    (ROOT / "index.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Indexed {len(entries)} distinct entries", flush=True)
    if not args.pages:
        return
    urls = sorted({urldefrag(e["url"])[0] for e in entries if args.match.casefold() in e["url"].casefold()})
    pages = ROOT / "pages"
    pages.mkdir(exist_ok=True)
    def download(url):
        path = pages / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if path.exists() and not args.refresh:
            return None
        try:
            raw, html = fetch(url)
            parsed = Page()
            parsed.feed(html)
            payload = {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "parser_version": 2,
                       "text": "\n".join(parsed.text)}
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
            return None
        except Exception as exc:
            return {"url": url, "error": str(exc)}
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, error in enumerate(pool.map(download, urls), 1):
            if error:
                errors.append(error)
            if i % 100 == 0:
                print(f"Processed {i}/{len(urls)}, failed {len(errors)}", flush=True)
    (ROOT / "download_errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    print(f"Pages processed {len(urls)}; failed {len(errors)}; cache {pages}", flush=True)


if __name__ == "__main__":
    main()

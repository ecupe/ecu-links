"""Optional: pull an account's own posts from the official Instagram API into its data file.

    set IG_ACCESS_TOKEN=<token>            (PowerShell: $env:IG_ACCESS_TOKEN = "<token>")
    py tools/sync_instagram.py mateoamendano

What it needs (none of this is set up yet, so the site works without it):
- The Instagram account must be a professional one (Creator or Business).
- A Meta developer app with "Instagram API with Instagram Login" and the
  `instagram_business_basic` permission, with the account added to it.
- A long-lived access token from that app. It lasts 60 days and must be refreshed before then.

The token is read from the IG_ACCESS_TOKEN environment variable only. Never put it in a file in
this repository, in the page, or in a commit. In GitHub Actions, store it as a repository secret.

What it does: asks for the account's media, saves a copy of each picture under
images/instagram/<handle>/ (Instagram's own image links expire), and merges the posts into
data/instagram/<handle>.json. Posts already in the file keep their `order`, `visible` and `alt`,
so your curation survives a sync. Highlights are never touched: no official API exposes them.

`--from-file response.json` reads a saved API response instead of calling the API (for trying
the merge without a token). The call to the live API has not been exercised yet, because there
is no token; check the first real run before relying on it.
"""
from pathlib import Path
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
API = "https://graph.instagram.com/me/media"
FIELDS = "id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp"
PERMALINK = re.compile(r"^https://www\.instagram\.com/(p|reel|tv)/([\w-]+)/?$")


def fetch(token, limit):
    query = urllib.parse.urlencode({"fields": FIELDS, "limit": limit, "access_token": token})
    with urllib.request.urlopen(f"{API}?{query}", timeout=30) as response:
        return json.load(response)


def kind(item):
    if item.get("media_product_type") == "REELS" or item.get("media_type") == "VIDEO":
        return "reel"
    return "carousel" if item.get("media_type") == "CAROUSEL_ALBUM" else "image"


def main():
    parser = argparse.ArgumentParser(description="Sync an Instagram account's posts into its data file.")
    parser.add_argument("handle")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--from-file", help="read a saved API response instead of calling the API")
    parser.add_argument("--no-images", action="store_true", help="do not download pictures (offline test)")
    args = parser.parse_args()

    if args.from_file:
        response = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
    else:
        token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
        if not token:
            sys.exit("Set IG_ACCESS_TOKEN first (see the notes at the top of this file).")
        response = fetch(token, args.limit)

    path = ROOT / "data" / "instagram" / f"{args.handle}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "handle": args.handle, "url": f"https://www.instagram.com/{args.handle}/", "posts": [], "highlights": []}
    known = {post.get("url"): post for post in data.get("posts", [])}
    folder = ROOT / "images" / "instagram" / args.handle
    added = updated = 0
    for item in response.get("data", []):
        match = PERMALINK.match(item.get("permalink", ""))
        picture = item.get("thumbnail_url") or item.get("media_url")
        if not match or not picture:
            print("skipped (no usable link or picture):", item.get("id"))
            continue
        url = f"https://www.instagram.com/{match.group(1)}/{match.group(2)}/"
        image = f"images/instagram/{args.handle}/{match.group(2)}.jpg"
        if not args.no_images:
            folder.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(picture, ROOT / image)
        fresh = {"id": match.group(2), "url": url, "image": image, "type": kind(item),
                 "caption": " ".join((item.get("caption") or "").split()), "date": (item.get("timestamp") or "")[:10]}
        if url in known:
            known[url].update(fresh)   # order, visible and alt stay as you set them
            updated += 1
        else:
            data.setdefault("posts", []).append({**fresh, "alt": "", "visible": True})
            added += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.handle}: {added} new, {updated} updated. Now run: py build.py")


if __name__ == "__main__":
    main()

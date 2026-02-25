"""Main scraper for Kindred Cocktails.

Usage:
    python scraper/scrape_kindred.py              # Full scrape
    python scraper/scrape_kindred.py --test 5      # Scrape only 5 recipes for testing
    python scraper/scrape_kindred.py --resume      # Resume from saved URL list, skip already-scraped
"""

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.login import create_session
from scraper.parse import (
    parse_cocktail_list_page,
    parse_recipe_page,
    get_total_pages,
    normalize_ingredient_name,
    BASE_URL,
)

USERNAME = "mpardaiolo"
PASSWORD = "lola6505"

LISTING_URL = "https://kindredcocktails.com/cocktail?scope=0&sort=name&page={page}"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "bar_cart.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
SUBS_PATH = os.path.join(BASE_DIR, "database", "substitutes.json")
URLS_CACHE = os.path.join(BASE_DIR, "database", "cocktail_urls.json")
REQUEST_DELAY = 1.5  # seconds between requests


def safe_print(msg):
    """Print with fallback encoding for Windows console."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def init_db():
    """Initialize the database with schema."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def get_or_create_ingredient(conn, display_name, match_name, kindred_url=""):
    """Get existing ingredient ID or create a new one."""
    row = conn.execute("SELECT id FROM ingredients WHERE match_name = ?", (match_name,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO ingredients (display_name, match_name, kindred_url) VALUES (?, ?, ?)",
        (display_name, match_name, kindred_url),
    )
    conn.commit()
    return cur.lastrowid


def upsert_cocktail(conn, recipe):
    """Insert or update a cocktail and its ingredients. Idempotent by source_url."""
    source_url = recipe["source_url"]

    row = conn.execute("SELECT id FROM cocktails WHERE source_url = ?", (source_url,)).fetchone()
    if row:
        cocktail_id = row[0]
        conn.execute(
            "UPDATE cocktails SET name=?, primary_spirit=?, instructions=? WHERE id=?",
            (recipe["name"], recipe["primary_spirit"], recipe["instructions"], cocktail_id),
        )
        conn.execute("DELETE FROM cocktail_ingredients WHERE cocktail_id = ?", (cocktail_id,))
    else:
        cur = conn.execute(
            "INSERT INTO cocktails (name, primary_spirit, instructions, source_url) VALUES (?, ?, ?, ?)",
            (recipe["name"], recipe["primary_spirit"], recipe["instructions"], source_url),
        )
        cocktail_id = cur.lastrowid

    for i, ing in enumerate(recipe["ingredients"]):
        ing_id = get_or_create_ingredient(
            conn, ing["display_name"], ing["match_name"], ing.get("kindred_url", "")
        )
        conn.execute(
            "INSERT INTO cocktail_ingredients (cocktail_id, ingredient_id, quantity, unit, sort_order) "
            "VALUES (?, ?, ?, ?, ?)",
            (cocktail_id, ing_id, ing["quantity"], ing["unit"], i),
        )

    conn.commit()
    return cocktail_id


def seed_substitutes(conn):
    """Seed the substitutes table from substitutes.json."""
    if not os.path.exists(SUBS_PATH):
        print("No substitutes.json found, skipping.")
        return

    with open(SUBS_PATH) as f:
        data = json.load(f)

    count = 0
    for group in data["substitutions"]:
        ingredients = group["ingredients"]
        note = group.get("note", "")

        ids = []
        for name in ingredients:
            display_name, match_name = normalize_ingredient_name(name)
            ing_id = get_or_create_ingredient(conn, display_name, match_name)
            ids.append(ing_id)

        for i, id_a in enumerate(ids):
            for j, id_b in enumerate(ids):
                if i != j:
                    conn.execute(
                        "INSERT OR IGNORE INTO substitutes (ingredient_id, substitute_id, note) "
                        "VALUES (?, ?, ?)",
                        (id_a, id_b, note),
                    )
                    count += 1

    conn.commit()
    print(f"Seeded {count} substitution pairs.")


def collect_cocktail_urls(session, use_cache=False):
    """Collect all cocktail URLs from listing pages. Caches to disk."""
    if use_cache and os.path.exists(URLS_CACHE):
        with open(URLS_CACHE) as f:
            urls = json.load(f)
        print(f"Loaded {len(urls)} cocktail URLs from cache.")
        return [(u["name"], u["url"]) for u in urls]

    print("Collecting cocktail URLs...")
    resp = session.get(LISTING_URL.format(page=0))
    resp.raise_for_status()

    total_pages = get_total_pages(resp.text)
    print(f"Total pages: {total_pages}")

    all_cocktails = parse_cocktail_list_page(resp.text)
    print(f"  Page 1/{total_pages}: {len(all_cocktails)} cocktails")

    for page in range(1, total_pages):
        time.sleep(REQUEST_DELAY)
        resp = session.get(LISTING_URL.format(page=page))
        resp.raise_for_status()
        page_cocktails = parse_cocktail_list_page(resp.text)
        all_cocktails.extend(page_cocktails)
        print(f"  Page {page + 1}/{total_pages}: {len(page_cocktails)} cocktails (total: {len(all_cocktails)})")

    # Deduplicate
    seen = set()
    unique = []
    for name, url in all_cocktails:
        if url not in seen:
            seen.add(url)
            unique.append((name, url))

    # Cache to disk
    with open(URLS_CACHE, "w") as f:
        json.dump([{"name": n, "url": u} for n, u in unique], f)

    print(f"Collected {len(unique)} unique cocktail URLs (cached to {URLS_CACHE}).")
    return unique


def scrape_recipes(session, conn, cocktail_urls, limit=None):
    """Scrape individual recipe pages and store in database."""
    if limit:
        cocktail_urls = cocktail_urls[:limit]

    total = len(cocktail_urls)
    print(f"\nScraping {total} cocktail recipes...")
    errors = []
    skipped = 0

    for i, (name, url) in enumerate(cocktail_urls):
        try:
            # Skip if already scraped
            row = conn.execute("SELECT id FROM cocktails WHERE source_url = ?", (url,)).fetchone()
            if row:
                skipped += 1
                if skipped <= 3 or skipped % 100 == 0:
                    safe_print(f"  [{i + 1}/{total}] Skipping (exists): {name}")
                continue

            time.sleep(REQUEST_DELAY)
            resp = session.get(url)
            resp.raise_for_status()

            recipe = parse_recipe_page(resp.text, url)
            if not recipe["name"]:
                recipe["name"] = name

            if recipe["ingredients"]:
                upsert_cocktail(conn, recipe)
                count_so_far = conn.execute("SELECT COUNT(*) FROM cocktails").fetchone()[0]
                safe_print(f"  [{i + 1}/{total}] {recipe['name']} "
                           f"({len(recipe['ingredients'])} ing) [DB: {count_so_far}]")
            else:
                safe_print(f"  [{i + 1}/{total}] WARNING: No ingredients for {name}")
                errors.append((name, url, "No ingredients parsed"))

        except KeyboardInterrupt:
            print(f"\n\nInterrupted! Progress saved. Re-run with --resume to continue.")
            break
        except Exception as e:
            safe_print(f"  [{i + 1}/{total}] ERROR: {name}: {e}")
            errors.append((name, url, str(e)))

    if errors:
        print(f"\n{len(errors)} errors:")
        for name, url, err in errors[:20]:
            safe_print(f"  - {name}: {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")

    cocktail_count = conn.execute("SELECT COUNT(*) FROM cocktails").fetchone()[0]
    ingredient_count = conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
    print(f"\nDatabase: {cocktail_count} cocktails, {ingredient_count} ingredients")
    if skipped:
        print(f"Skipped {skipped} already-scraped cocktails.")


def main():
    parser = argparse.ArgumentParser(description="Scrape Kindred Cocktails")
    parser.add_argument("--test", type=int, help="Limit to N recipes for testing")
    parser.add_argument("--resume", action="store_true", help="Resume using cached URL list")
    args = parser.parse_args()

    conn = init_db()
    print(f"Database: {DB_PATH}")

    seed_substitutes(conn)

    session = create_session(USERNAME, PASSWORD)

    cocktail_urls = collect_cocktail_urls(session, use_cache=args.resume)
    scrape_recipes(session, conn, cocktail_urls, limit=args.test)

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()

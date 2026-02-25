"""Quick inspection script to understand Kindred Cocktails HTML structure."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.login import create_session

USERNAME = "mpardaiolo"
PASSWORD = "lola6505"


def inspect():
    session = create_session(USERNAME, PASSWORD)

    # Check how many cocktails per page when logged in
    resp = session.get("https://kindredcocktails.com/cocktail?scope=0&sort=name&page=0")
    resp.raise_for_status()

    # Save listing page HTML for inspection
    with open("listing_sample.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print(f"Saved listing page ({len(resp.text)} bytes)")

    # Count cocktail links on the page
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "lxml")
    links = [a for a in soup.find_all("a", href=True) if a["href"].startswith("/cocktail/") and a["href"].count("/") == 2]
    print(f"Cocktails on page: {len(links)}")

    # Get pagination info
    last = soup.find("a", title=lambda t: t and "last" in t.lower())
    if last:
        print(f"Last page link: {last.get('href')}")

    # Save a recipe page for inspection
    resp2 = session.get("https://kindredcocktails.com/cocktail/negroni")
    resp2.raise_for_status()
    with open("recipe_sample.html", "w", encoding="utf-8") as f:
        f.write(resp2.text)
    print(f"Saved recipe page ({len(resp2.text)} bytes)")

    # Print the recipe section structure
    soup2 = BeautifulSoup(resp2.text, "lxml")

    # Find ingredient-related elements
    print("\n=== INGREDIENT SECTION ===")
    # Look for common Drupal field patterns
    for div in soup2.find_all("div", class_=True):
        classes = " ".join(div.get("class", []))
        if "ingredient" in classes.lower() or "recipe" in classes.lower():
            print(f"  <div class='{classes}'>")
            # Show first 500 chars of inner HTML
            inner = str(div)[:500]
            print(f"    {inner}")
            print()

    # Look for the preparation/instructions
    print("\n=== INSTRUCTIONS SECTION ===")
    for div in soup2.find_all("div", class_=True):
        classes = " ".join(div.get("class", []))
        if any(w in classes.lower() for w in ["preparation", "instruction", "method", "direction"]):
            print(f"  <div class='{classes}'>")
            print(f"    {div.get_text(strip=True)[:300]}")
            print()

    # Also look for field-name patterns (Drupal)
    print("\n=== DRUPAL FIELD PATTERNS ===")
    for div in soup2.find_all("div", class_=lambda c: c and any("field-name" in x for x in c)):
        classes = " ".join(div.get("class", []))
        text = div.get_text(strip=True)[:200]
        print(f"  <div class='{classes}'> -> {text}")


if __name__ == "__main__":
    inspect()

"""HTML parsing utilities for Kindred Cocktails."""

import re
from bs4 import BeautifulSoup

BASE_URL = "https://kindredcocktails.com"

# Map variant spirit names to canonical primary spirit
SPIRIT_MAP = {
    "whisky": "Whiskey",
    "bourbon": "Whiskey",
    "rye": "Whiskey",
    "rye whiskey": "Whiskey",
    "scotch": "Whiskey",
    "scotch whisky": "Whiskey",
    "irish whiskey": "Whiskey",
    "japanese whisky": "Whiskey",
    "blended whiskey": "Whiskey",
    "cognac": "Brandy",
    "pisco": "Brandy",
    "armagnac": "Brandy",
    "calvados": "Brandy",
    "applejack": "Brandy",
    "apple brandy": "Brandy",
    "mezcal": "Tequila",
    "cachaça": "Rum",
    "cachaca": "Rum",
    "rhum agricole": "Rum",
}

PRIMARY_SPIRIT_KEYWORDS = [
    "gin", "whiskey", "whisky", "bourbon", "rye", "scotch",
    "rum", "tequila", "mezcal", "vodka", "brandy", "cognac",
    "pisco", "absinthe", "aquavit", "cachaça", "cachaca",
]


def normalize_ingredient_name(name):
    """Normalize an ingredient name for matching.

    Returns (display_name, match_name) tuple.
    """
    display_name = name.strip()
    match_name = display_name.lower()

    # Remove common prefixes that create duplicates
    for prefix in ["fresh ", "freshly squeezed ", "freshly pressed "]:
        if match_name.startswith(prefix):
            match_name = match_name[len(prefix):]
            break

    match_name = re.sub(r"\s+", " ", match_name).strip()
    return display_name, match_name


def detect_primary_spirit(ingredient_names):
    """Detect the primary spirit from ingredient list (first spirit wins)."""
    for ing_name in ingredient_names:
        name_lower = ing_name.lower().strip()
        if name_lower in SPIRIT_MAP:
            return SPIRIT_MAP[name_lower]
        for kw in PRIMARY_SPIRIT_KEYWORDS:
            if kw in name_lower:
                return SPIRIT_MAP.get(kw, kw.capitalize())
    return None


def parse_cocktail_list_page(html):
    """Parse a cocktail listing page. Returns list of (name, url) tuples."""
    soup = BeautifulSoup(html, "lxml")
    cocktails = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("/cocktail/") and href.count("/") == 2:
            name = link.get_text(strip=True)
            if name:
                cocktails.append((name, BASE_URL + href))
    return cocktails


def get_total_pages(html):
    """Extract total number of pages from a cocktail listing page."""
    soup = BeautifulSoup(html, "lxml")
    last_link = soup.find("a", title=lambda t: t and "last" in t.lower() if t else False)
    if last_link:
        href = last_link.get("href", "")
        match = re.search(r"page=(\d+)", href)
        if match:
            return int(match.group(1)) + 1
    return 0


def parse_recipe_page(html, url=""):
    """Parse a single cocktail recipe page.

    Returns a dict with: name, ingredients, instructions, source_url, primary_spirit
    """
    soup = BeautifulSoup(html, "lxml")
    recipe = {
        "name": "",
        "ingredients": [],
        "instructions": "",
        "source_url": url,
        "primary_spirit": None,
    }

    # Get cocktail name
    title = soup.find("h1")
    if title:
        recipe["name"] = title.get_text(strip=True)

    # Parse ingredients from field--name-ingredients
    ingredient_names = []
    ing_container = soup.find("div", class_="field--name-ingredients")
    if ing_container:
        for item in ing_container.find_all("div", class_="field__item"):
            ing = _parse_ingredient_item(item)
            if ing:
                recipe["ingredients"].append(ing)
                ingredient_names.append(ing["display_name"])

    recipe["primary_spirit"] = detect_primary_spirit(ingredient_names)

    # Parse instructions from field--name-cocktail-instructions
    inst_container = soup.find("div", class_="field--name-cocktail-instructions")
    if inst_container:
        inst_item = inst_container.find("div", class_="field__item")
        if inst_item:
            recipe["instructions"] = inst_item.get_text(strip=True)
        else:
            # Fallback: get text after the label
            label = inst_container.find("div", class_="field__label")
            text = inst_container.get_text(strip=True)
            if label:
                label_text = label.get_text(strip=True)
                if text.startswith(label_text):
                    text = text[len(label_text):].strip()
            recipe["instructions"] = text

    return recipe


def _parse_ingredient_item(item):
    """Parse a single ingredient field__item div.

    Expected structure:
        <div class="field__item">
            <span class="quantity-unit">1 <abbr title="ounce">oz</abbr></span>
            <span class="ingredient-name">
                <a href="/ingredient/gin">Gin</a> (optional note)
            </span>
        </div>
    """
    # Get ingredient name from the link
    link = item.find("a", href=re.compile(r"/ingredient/"))
    if not link:
        return None

    ing_name = link.get_text(strip=True)
    if not ing_name:
        return None

    display_name, match_name = normalize_ingredient_name(ing_name)

    # Get quantity and unit from quantity-unit span
    quantity = ""
    unit = ""
    qty_span = item.find("span", class_="quantity-unit")
    if qty_span:
        qty_text = qty_span.get_text(strip=True)
        # Extract the unit from the abbr title if present
        abbr = qty_span.find("abbr")
        if abbr:
            unit = abbr.get("title", abbr.get_text(strip=True)).strip().lower()
            # The quantity is everything before the abbr text
            abbr_text = abbr.get_text(strip=True)
            idx = qty_text.find(abbr_text)
            if idx > 0:
                quantity = qty_text[:idx].strip()
            else:
                quantity = qty_text.replace(abbr_text, "").strip()
        else:
            # No abbr, the whole span is the quantity
            quantity = qty_text

    # Normalize unit names
    unit = _normalize_unit(unit)

    kindred_url = link.get("href", "")
    if kindred_url.startswith("/"):
        kindred_url = BASE_URL + kindred_url

    return {
        "display_name": display_name,
        "match_name": match_name,
        "quantity": quantity,
        "unit": unit,
        "kindred_url": kindred_url,
    }


def _normalize_unit(unit):
    """Normalize unit abbreviations to consistent names."""
    unit_map = {
        "ounce": "oz",
        "ounces": "oz",
        "ds": "dash",
        "dash": "dash",
        "dashes": "dash",
        "drop": "drop",
        "drops": "drop",
        "teaspoon": "tsp",
        "tablespoon": "tbsp",
        "barspoon": "barspoon",
        "barspoons": "barspoon",
        "twist": "twist",
        "twst": "twist",
        "peel": "peel",
        "slice": "slice",
        "sprig": "sprig",
        "leaf": "leaf",
        "leaves": "leaf",
        "piece": "piece",
        "wedge": "wedge",
        "wheel": "wheel",
        "rinse": "rinse",
        "spray": "spray",
        "cube": "cube",
        "part": "part",
        "parts": "part",
        "cup": "cup",
        "ml": "ml",
        "cl": "cl",
        "unknown": "",
        "?": "",
    }
    return unit_map.get(unit.lower(), unit.lower()) if unit else ""

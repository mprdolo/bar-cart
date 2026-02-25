"""One-time migration: fix categories, add general_id for brand ingredients,
mark always-available categories/ingredients."""
import sqlite3
from config import DATABASE_PATH


# --- Category fixes ---
# (match_name, correct_category_id)
CATEGORY_FIXES = [
    # Ginger items incorrectly in Gin (cat 2) — move to correct categories
    ("ginger syrup", 12),        # Sweetener
    ("ginger liqueur", 9),       # Liqueur
    ("ginger ale", 16),          # Sodas & Waters
    ("ginger beer", 16),         # Sodas & Waters
    ("ginger", 13),              # Fruit & Produce
    ("ginger vodka", 5),         # Vodka
    ("ginger shrub", 12),        # Sweetener
    # Orange Curacao in Citrus -> Liqueurs
    ("orange cura\xe7ao", 9),
    # Fee Brothers Cherry in Fruit -> Bitters
    ("fee brothers cherry", 10),
    # Lemon Hart 151 is a rum, not citrus
    ("lemon hart 151", 3),
    # Lemonade is a soda, not citrus
    ("lemonade", 16),
    # Bitter lemon soda is a soda, not citrus
    ("bitter lemon soda", 16),
    # Orange blossom jam is a sweetener
    ("orange blossom jam", 12),
    # Orange marmalade is a sweetener
    ("orange marmalade", 12),
    # Orange flower water -> Garnishes (it's a flavoring)
    ("orange flower water", 14),
    # Orange mint -> Garnishes
    ("orange mint", 14),
    # Irish cream -> Liqueur (not dairy)
    ("irish cream", 9),
]

# --- Brand -> General mappings ---
# (brand_match_name, general_match_name)
# These set general_id so the bar page hides brands and recipes match at general level.
BRAND_TO_GENERAL = [
    # Whiskey brands -> general types
    ("talisker", "scotch"),
    ("macallan", "scotch"),
    ("macallan 10", "scotch"),
    ("macallan 12", "scotch"),
    ("glenmorangie", "scotch"),
    ("balvenie 12 doublewood", "scotch"),
    ("springbank 10", "scotch"),
    ("booker's", "bourbon"),
    ("michter's", "bourbon"),
    ("high west silver whiskey", "whiskey"),
    # Rum brands -> general types
    ("smith & cross", "jamaican rum"),
    ("appleton v/x", "jamaican rum"),
    ("gosling's black seal", "dark rum"),
    ("pusser's", "dark rum"),
    ("old monk", "dark rum"),
    ("cruzan blackstrap", "dark rum"),
    ("barbancourt", "rum"),
    ("barbancourt 8", "rum"),
    ("barbancourt white", "light rum"),
    ("brugal", "rum"),
    ("cruzan", "light rum"),
    ("cruzan aged light", "light rum"),
    ("cruzan single barrel", "rum"),
    ("zacapa", "rum"),
    ("zacapa 23", "rum"),
    ("matusalem platino", "light rum"),
    ("matusalem gran reserva", "rum"),
    ("flor de ca\xf1a", "rum"),
    ("flor de ca\xf1a 7", "rum"),
    ("flor de ca\xf1a dry 4", "light rum"),
    ("flor de ca\xf1a extra dry", "light rum"),
    ("flor de ca\xf1a gold 4", "gold rum"),
    ("cl\xe9ment", "rhum agricole"),
    ("cl\xe9ment vsop", "rhum agricole"),
    ("la favorite", "rhum agricole"),
    ("la favorite blanc", "rhum agricole"),
    ("la favorite vieux", "rhum agricole"),
    ("don's mix", "rum"),
    ("donn's spices #2", "rum"),
    # Tequila brands
    ("del maguey", "mezcal"),
    ("agavero", "tequila"),
    # Vodka brands
    ("skyy", "vodka"),
    # Brandy brands
    ("clear creek", "pear eau de vie"),
    ("trimbach", "pear eau de vie"),
    # Vermouth brands -> general types
    ("cocchi vermouth di torino", "sweet vermouth"),
    ("carpano antica formula", "sweet vermouth"),
    ("carpano punt e mes", "sweet vermouth"),
    ("punt e mes", "sweet vermouth"),
    ("noilly prat ambre", "dry vermouth"),
    ("cocchi", "sweet vermouth"),
    ("gruet", "champagne"),
    # Liqueur brands -> general types
    ("luxardo", "maraschino liqueur"),
    ("giffard", "elderflower liqueur"),
    ("leopold brothers", "maraschino liqueur"),
    ("briottet", "apricot liqueur"),
    ("mathilde", "pear liqueur"),
    ("chambers", "elderflower liqueur"),
    ("bols", "orange liqueur"),
    ("cinzano orancio", "orange liqueur"),
    ("mozart black", "chocolate liqueur"),
    # Sweetener brands
    ("b.g. reynolds", "simple syrup"),
    ("monin", "simple syrup"),
    ("rose's", "grenadine"),
    ("bonne maman", "simple syrup"),
    ("thatcher's", "simple syrup"),
    # Amaro brands used as general
    ("nardini", "amaro nardini"),  # already specific enough
    ("luxardo fernet", "fernet branca"),
    # Bitters brands
    ("sap56", "bitters"),
]

# --- Always-available categories ---
# These entire categories are assumed always in stock.
ALWAYS_AVAILABLE_CATEGORIES = [
    17,  # Other (ice)
    14,  # Garnishes
    13,  # Fruit & Produce
]

# --- Always-available specific ingredients (by match_name) ---
# From other categories, always assumed in stock.
ALWAYS_AVAILABLE_ITEMS = [
    # Sodas & Waters
    "water", "seltzer water", "sparkling water", "soda water",
    # Dairy & Eggs
    "egg white", "egg yolk", "whole egg", "butter",
    # Sweeteners
    "sugar", "sugar cube", "brown sugar", "demerara sugar",
    "simple syrup", "rich simple syrup", "rich simple syrup 2:1",
    # Citrus
    "lemon", "lemon juice", "lemon peel", "lemon zest",
    "orange", "orange juice", "orange peel",
    "lime juice",
]


def migrate():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    c = conn.cursor()

    # 1. Add columns if they don't exist
    _add_column(c, "ingredients", "general_id", "INTEGER REFERENCES ingredients(id)")
    _add_column(c, "ingredients", "always_available", "INTEGER DEFAULT 0")
    _add_column(c, "categories", "always_available", "INTEGER DEFAULT 0")

    # 2. Fix category assignments
    print("Fixing category assignments...")
    for match_name, cat_id in CATEGORY_FIXES:
        c.execute("UPDATE ingredients SET category_id = ? WHERE match_name = ?", (cat_id, match_name))
        if c.rowcount:
            print(f"  {match_name} -> category {cat_id}")

    # 3. Set brand -> general mappings
    print("\nSetting brand -> general mappings...")
    # Build match_name -> id lookup
    c.execute("SELECT id, match_name FROM ingredients")
    name_to_id = {row[1]: row[0] for row in c.fetchall()}

    mapped = 0
    for brand_name, general_name in BRAND_TO_GENERAL:
        brand_id = name_to_id.get(brand_name)
        general_id = name_to_id.get(general_name)
        if brand_id and general_id:
            c.execute("UPDATE ingredients SET general_id = ? WHERE id = ?", (general_id, brand_id))
            mapped += 1
        elif brand_id and not general_id:
            print(f"  WARNING: general '{general_name}' not found for brand '{brand_name}'")
        # brand not found is OK (may not exist in DB)

    print(f"  Mapped {mapped} brand ingredients to generals")

    # 4. Mark always-available categories
    print("\nMarking always-available categories...")
    for cat_id in ALWAYS_AVAILABLE_CATEGORIES:
        c.execute("UPDATE categories SET always_available = 1 WHERE id = ?", (cat_id,))
        c.execute("UPDATE ingredients SET always_available = 1 WHERE category_id = ?", (cat_id,))
        c.execute("SELECT COUNT(*) FROM ingredients WHERE category_id = ?", (cat_id,))
        cnt = c.fetchone()[0]
        c.execute("SELECT name FROM categories WHERE id = ?", (cat_id,))
        name = c.fetchone()[0]
        print(f"  {name}: {cnt} ingredients")

    # 5. Mark always-available specific items
    print("\nMarking always-available specific items...")
    for match_name in ALWAYS_AVAILABLE_ITEMS:
        c.execute("UPDATE ingredients SET always_available = 1 WHERE match_name = ?", (match_name,))
        if c.rowcount:
            print(f"  {match_name}")

    conn.commit()

    # Report
    c.execute("SELECT COUNT(*) FROM ingredients WHERE general_id IS NOT NULL")
    print(f"\nTotal brand ingredients with general mapping: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM ingredients WHERE always_available = 1")
    print(f"Total always-available ingredients: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM ingredients WHERE general_id IS NULL AND always_available = 0")
    print(f"Ingredients shown in bar page: {c.fetchone()[0]}")

    conn.close()
    print("\nDone!")


def _add_column(cursor, table, column, definition):
    try:
        cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"Added column {table}.{column}")


if __name__ == "__main__":
    migrate()

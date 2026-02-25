"""One-time script to populate categories and assign category_id to all ingredients."""
import sqlite3
from config import DATABASE_PATH

CATEGORIES = [
    (1, "Whiskey", 1),
    (2, "Gin", 2),
    (3, "Rum", 3),
    (4, "Tequila & Mezcal", 4),
    (5, "Vodka", 5),
    (6, "Brandy & Cognac", 6),
    (7, "Wine & Vermouth", 7),
    (8, "Amari & Aperitifs", 8),
    (9, "Liqueurs", 9),
    (10, "Bitters", 10),
    (11, "Citrus", 11),
    (12, "Sweeteners", 12),
    (13, "Fruit & Produce", 13),
    (14, "Garnishes", 14),
    (15, "Dairy & Eggs", 15),
    (16, "Sodas & Waters", 16),
    (17, "Other", 17),
]

# Exact-match overrides for specific ingredients (checked first).
EXACT = {
    "rye": 1,                       # Whiskey (not a fruit)
    "glenmorangie": 1,
    "macallan": 1,
    "macallan 10": 1,
    "macallan 12": 1,
    "michter's": 1,
    "appleton v/x": 3,              # Rum
    "gosling's black seal": 3,
    "cruzan": 3,
    "cruzan aged light": 3,
    "cruzan blackstrap": 3,
    "cruzan single barrel": 3,
    "pusser's": 3,
    "old monk": 3,
    "brugal": 3,
    "cl\u00e9ment": 3,
    "cl\u00e9ment vsop": 3,
    "la favorite": 3,
    "la favorite blanc": 3,
    "la favorite vieux": 3,
    "matusalem gran reserva": 3,
    "matusalem platino": 3,
    "don's mix": 3,
    "donn's spices #2": 3,
    "del maguey": 4,                # Mezcal brand
    "poire william": 6,             # Brandy
    "clear creek": 6,
    "carpano antica formula": 7,    # Vermouth
    "carpano punt e mes": 7,
    "punt e mes": 7,
    "cocchi": 7,
    "cocchi americano": 7,
    "cocchi americano rosa": 7,
    "cocchi barolo chinato": 7,
    "noilly prat ambre": 7,
    "byrrh": 8,                     # Amari & Aperitifs
    "branca menta": 8,
    "centerbe": 8,
    "chinato": 8,
    "ciociaro": 8,
    "ramazzotti": 8,
    "maurin quina": 8,
    "mirto": 8,
    "nardini": 8,
    "luxardo bitter rosso": 8,
    "j\u00e4germeister": 8,
    "pimm's no. 1 cup": 8,
    "b\u00e9n\u00e9dictine": 9,     # Liqueurs
    "b\u00e4renj\u00e4ger": 9,
    "cr\u00e8me yvette": 9,
    "cassis": 9,
    "framboise": 9,
    "luxardo": 9,
    "mandarine napoleon": 9,
    "mozart black": 9,
    "ouzo": 9,
    "pacharan": 9,
    "parfait amour": 9,
    "pastis": 9,
    "pernod": 9,
    "qi": 9,
    "raki": 9,
    "mekhong": 9,
    "chinotto": 9,
    "cinzano orancio": 9,
    "giffard": 9,
    "leopold brothers": 9,
    "mathilde": 9,
    "monin": 12,                    # Sweetener (syrup brand)
    "b.g. reynolds": 12,
    "bols": 9,
    "briottet": 9,
    "chambers": 9,
    "fee brothers": 10,             # Bitters brand
    "black balsams": 10,
    "rose's": 12,                   # Sweetener (Rose's lime etc)
    "bonne maman": 12,
    "thatcher's": 12,
    "coco l\u00f3pez": 12,
    "sap56": 12,
    "apricot": 13,                  # Fruit
    "cantaloupe": 13,
    "fruit": 13,
    "plum": 13,
    "tangerine peel": 14,           # Garnish
    "cardamom": 14,
    "coriander": 14,
    "cocktail onion": 14,
    "fennel seeds": 14,
    "green chile": 14,
    "oregano": 14,
    "raisins": 14,
    "candycane": 14,
    "espresso": 14,
    "ale": 16,                      # Beer -> Sodas & Waters
    "beer": 16,
    "lager": 16,
    "pale ale": 16,
    "stout": 16,
    "root beer": 16,
    "gruet": 7,                     # Sparkling wine brand
    "cacha\xe7a": 3,                  # Latin-1 encoded cachaça -> Rum
    "cura\xe7ao": 9,                  # Latin-1 encoded curaçao -> Liqueurs
    "blue cura\xe7ao": 9,
    "ice": 17,
    "ice cubes": 17,
    "crushed ice": 17,
    "elisir m. p. roux": 8,
    "flor de ca\u00f1a": 3,
    "flor de ca\u00f1a 7": 3,
    "flor de ca\u00f1a dry 4": 3,
    "flor de ca\u00f1a extra dry": 3,
    "flor de ca\u00f1a gold 4": 3,
}

# Rules: list of (category_id, keywords). First match wins.
# Keywords are matched against match_name.
RULES = [
    # --- Bitters (before spirits, since "orange bitters" shouldn't match liqueurs) ---
    (10, [
        "bitters", "angostura", "peychaud", "bittermens", "bittercube",
        "bitter end", "underberg",
    ]),

    # --- Whiskey ---
    (1, [
        "whiskey", "whisky", "bourbon", "rye whiskey", "scotch",
        "tennessee whiskey", "blended whiskey", "blended scotch",
        "balvenie", "springbank", "talisker", "booker's",
        "irish whiskey",
    ]),

    # --- Gin ---
    (2, [
        "gin", "sloe gin", "genever", "old tom gin", "plymouth gin",
    ]),

    # --- Rum ---
    (3, [
        "rum", "rhum", "cachac", "batavia arrack",
        "falernum", "barbancourt", "smith & cross", "zacapa",
    ]),

    # --- Tequila & Mezcal ---
    (4, [
        "tequila", "mezcal", "agavero",
    ]),

    # --- Vodka ---
    (5, [
        "vodka", "skyy",
    ]),

    # --- Brandy & Cognac ---
    (6, [
        "brandy", "cognac", "armagnac", "calvados", "applejack",
        "apple brandy", "pisco", "grappa", "eau de vie", "kirsch",
        "kirschwasser", "poire williams", "blume marillen",
        "slivovitz", "trimbach",
    ]),

    # --- Wine & Vermouth ---
    (7, [
        "vermouth", "sherry", "port", "wine", "champagne", "prosecco",
        "cava", "lillet", "pineau des charentes", "sake", "riesling",
        "dubonnet", "madeira", "marsala", "mead",
    ]),

    # --- Amari & Aperitifs ---
    (8, [
        "amaro", "aperol", "campari", "cynar", "fernet", "averna",
        "amer picon", "bonal", "suze", "becherovka", "strega",
        "swedish punsch", "zwack", "zucca", "sanbitter",
        "gran classico", "china china", "gentiane",
    ]),

    # --- Liqueurs ---
    (9, [
        "liqueur", "chartreuse", "maraschino", "curac", "curacao",
        "triple sec", "cointreau", "grand marnier", "absinthe",
        "benedictine", "drambuie", "amaretto", "frangelico",
        "kahlua", "coffee liqueur", "sambuca", "anisette",
        "galliano", "midori", "chambord", "creme de", "cr\u00e8me de",
        "advocaat", "baileys", "amarula",
        "st-germain", "st. germain", "elderflower",
        "dram", "velvet falernum", "tuaca", "domaine de canton",
        "pama", "hpnotiq", "limoncello", "nocino",
        "aquavit", "apfelkorn", "rompope", "shochu", "zirbenz",
    ]),

    # --- Citrus ---
    (11, [
        "lemon juice", "lime juice", "orange juice", "grapefruit juice",
        "lemon", "lime", "orange", "grapefruit", "yuzu",
        "blood orange", "tangerine juice",
    ]),

    # --- Sweeteners ---
    (12, [
        "syrup", "sugar", "honey", "agave", "molasses", "grenadine",
        "maple", "orgeat", "marmalade", "jam", "jelly", "preserves",
        "shrub", "cordial", "oleo saccharum", "demerara",
    ]),

    # --- Dairy & Eggs ---
    (15, [
        "egg", "cream", "milk", "butter", "yogurt",
    ]),

    # --- Sodas & Waters ---
    (16, [
        "soda", "tonic", "cola", "ginger ale", "ginger beer",
        "seltzer", "sparkling water", "water", "lemonade",
        "bitter lemon",
    ]),

    # --- Fruit & Produce ---
    (13, [
        "apple", "banana", "berry", "blueberry", "blackberry",
        "strawberry", "raspberry", "cherry", "peach", "pear",
        "pineapple", "mango", "coconut", "watermelon", "melon",
        "fig", "grape", "cranberry", "pomegranate", "passion fruit",
        "guava", "papaya", "cucumber", "celery", "tomato",
        "carrot", "ginger", "jalap", "pepper", "olive",
        "rhubarb", "tamarind", "puree", "juice",
        "cider",
    ]),

    # --- Garnishes ---
    (14, [
        "basil", "mint", "rosemary", "thyme", "sage", "tarragon",
        "cilantro", "dill", "lavender", "hibiscus", "rose",
        "cinnamon", "nutmeg", "clove", "allspice", "star anise",
        "anise", "vanilla", "salt", "pepper", "peppercorn",
        "tea", "coffee", "chocolate", "cocoa", "worcestershire",
        "soy sauce", "vinegar", "tabasco", "hot sauce",
    ]),
]


def categorize():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    c = conn.cursor()

    # Clear existing category assignments, then repopulate categories
    c.execute("UPDATE ingredients SET category_id = NULL")
    c.execute("DELETE FROM categories")
    for cat_id, name, sort_order in CATEGORIES:
        c.execute(
            "INSERT INTO categories (id, name, sort_order) VALUES (?, ?, ?)",
            (cat_id, name, sort_order),
        )

    # Load all ingredients
    c.execute("SELECT id, match_name FROM ingredients")
    ingredients = c.fetchall()

    categorized = 0
    uncategorized = []

    for ing_id, match_name in ingredients:
        cat_id = _match_category(match_name)
        c.execute("UPDATE ingredients SET category_id = ? WHERE id = ?", (cat_id, ing_id))
        if cat_id == 17:
            uncategorized.append(match_name)
        else:
            categorized += 1

    conn.commit()

    # Report
    total = len(ingredients)
    print(f"Categorized {categorized}/{total} ingredients")
    if uncategorized:
        print(f"\n{len(uncategorized)} assigned to 'Other':")
        for name in sorted(uncategorized):
            print(f"  - {name}")

    # Category counts
    c.execute("""
        SELECT c.name, COUNT(i.id) as cnt
        FROM categories c
        LEFT JOIN ingredients i ON i.category_id = c.id
        GROUP BY c.id
        ORDER BY c.sort_order
    """)
    print("\nCategory counts:")
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}")

    conn.close()


def _match_category(match_name):
    """Return category_id for an ingredient match_name. Exact overrides first, then keyword rules."""
    name = match_name.lower()
    # Check exact overrides first
    if name in EXACT:
        return EXACT[name]
    # Then keyword substring rules
    for cat_id, keywords in RULES:
        for kw in keywords:
            if kw in name:
                return cat_id
    return 17  # Other


if __name__ == "__main__":
    categorize()

"""Cocktail matching algorithm — finds cocktails you can make with your bar stock."""
from db import get_db_connection


def find_matches():
    """Return cocktails grouped by match tier: perfect, substitute, close.

    - PERFECT: all ingredients in stock
    - SUBSTITUTE: all ingredients covered by stock + substitutes
    - CLOSE: exactly 1 ingredient missing (no substitute available)
    - Skip anything missing 2+ ingredients

    Always-available ingredients and general_id mappings are factored in
    so brand ingredients match against their general counterpart.
    """
    conn = get_db_connection()
    try:
        # 1. Load stocked ingredient IDs + always-available
        stocked = set()
        for row in conn.execute("SELECT ingredient_id FROM bar_stock"):
            stocked.add(row["ingredient_id"])
        for row in conn.execute("SELECT id FROM ingredients WHERE always_available = 1"):
            stocked.add(row["id"])

        if not stocked:
            return {"perfect": [], "substitute": [], "close": [], "stocked_count": 0}

        # 2. Build general_id lookup: brand_id -> general_id
        general_map = {}
        for row in conn.execute("SELECT id, general_id FROM ingredients WHERE general_id IS NOT NULL"):
            general_map[row["id"]] = row["general_id"]

        # 3. Build substitute lookup: ingredient_id -> set of substitute_ids
        subs = {}
        for row in conn.execute("SELECT ingredient_id, substitute_id FROM substitutes"):
            subs.setdefault(row["ingredient_id"], set()).add(row["substitute_id"])

        # 4. Bulk-load all cocktail ingredients (~44K rows) with names
        cocktail_ingredients = {}
        for row in conn.execute("""
            SELECT ci.cocktail_id, ci.ingredient_id, i.display_name
            FROM cocktail_ingredients ci
            JOIN ingredients i ON i.id = ci.ingredient_id
            ORDER BY ci.cocktail_id, ci.sort_order
        """):
            cocktail_ingredients.setdefault(row["cocktail_id"], []).append(
                (row["ingredient_id"], row["display_name"])
            )

        # 5. Load cocktail metadata
        cocktails = {}
        for row in conn.execute("SELECT id, name, primary_spirit FROM cocktails"):
            cocktails[row["id"]] = {
                "id": row["id"],
                "name": row["name"],
                "primary_spirit": row["primary_spirit"],
            }

        # 5b. Bulk-load average ratings
        avg_ratings = {}
        for row in conn.execute("SELECT cocktail_id, AVG(score) as avg FROM ratings GROUP BY cocktail_id"):
            avg_ratings[row["cocktail_id"]] = round(row["avg"], 1)

        # 6. Classify each cocktail
        perfect = []
        substitute = []
        close = []

        for cid, ing_tuples in cocktail_ingredients.items():
            if cid not in cocktails:
                continue

            have = []
            sub_used = []
            missing = []
            all_names = []

            for iid, iname in ing_tuples:
                all_names.append(iname)
                if _is_stocked(iid, stocked, general_map):
                    have.append(iid)
                elif _has_substitute(iid, stocked, subs, general_map):
                    sub_used.append(iid)
                else:
                    missing.append((iid, iname))

            missing_count = len(missing)
            base = {
                **cocktails[cid],
                "total_ingredients": len(ing_tuples),
                "ingredient_names": all_names,
                "have_count": len(have),
                "sub_count": len(sub_used),
                "avg_rating": avg_ratings.get(cid),
            }

            if missing_count == 0 and len(sub_used) == 0:
                perfect.append({**base, "tier": "perfect",
                    "missing_count": 0, "missing_ingredients": []})
            elif missing_count == 0 and len(sub_used) > 0:
                substitute.append({**base, "tier": "substitute",
                    "missing_count": 0, "missing_ingredients": []})
            elif missing_count == 1:
                close.append({**base, "tier": "close",
                    "missing_count": 1,
                    "missing_ingredients": [{"id": missing[0][0], "name": missing[0][1]}],
                })

        perfect.sort(key=lambda x: x["name"].lower())
        substitute.sort(key=lambda x: x["name"].lower())
        close.sort(key=lambda x: x["name"].lower())

        # Stocked count: only user-stocked, not auto-available
        user_stocked = conn.execute("SELECT COUNT(*) FROM bar_stock").fetchone()[0]

        return {
            "perfect": perfect,
            "substitute": substitute,
            "close": close,
            "stocked_count": user_stocked,
        }
    finally:
        conn.close()


def _is_stocked(ingredient_id, stocked, general_map):
    """Check if ingredient is in stock (directly or via general mapping)."""
    if ingredient_id in stocked:
        return True
    general_id = general_map.get(ingredient_id)
    if general_id and general_id in stocked:
        return True
    return False


def _has_substitute(ingredient_id, stocked, subs, general_map):
    """Check if any substitute for this ingredient is in stock."""
    sub_ids = subs.get(ingredient_id, set())
    for sid in sub_ids:
        if _is_stocked(sid, stocked, general_map):
            return True
    return False


def _get_ingredient_names(conn, ids):
    """Fetch display_name for a set of ingredient IDs."""
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id, display_name FROM ingredients WHERE id IN ({placeholders})",
        list(ids),
    ).fetchall()
    return {row["id"]: row["display_name"] for row in rows}

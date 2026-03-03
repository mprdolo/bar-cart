import threading
from flask import Flask, jsonify, request, render_template, redirect, url_for
from config import SECRET_KEY
from db import get_db_connection
from shake import find_matches

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Migrate: add comment column to ratings if missing
try:
    _conn = get_db_connection()
    _conn.execute("ALTER TABLE ratings ADD COLUMN comment TEXT")
    _conn.commit()
    _conn.close()
except Exception:
    pass  # column already exists

# Migrate: create dismissed_cocktails table if missing
try:
    _conn = get_db_connection()
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS dismissed_cocktails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cocktail_id INTEGER NOT NULL UNIQUE,
            date_dismissed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cocktail_id) REFERENCES cocktails(id)
        )
    """)
    _conn.commit()
    _conn.close()
except Exception:
    pass

# Track sync state
sync_status = {"in_progress": False, "message": "", "current": 0, "total": 0}
sync_lock = threading.Lock()


def api_response(success=True, data=None, message="", status_code=200):
    """Standard JSON response wrapper."""
    return jsonify({"success": success, "data": data, "message": message}), status_code


# --- Page routes ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/bar")
def bar_page():
    return render_template("bar.html")


@app.route("/results")
def results_page():
    return render_template("results.html")


@app.route("/recipe/<int:cocktail_id>")
def recipe_page(cocktail_id):
    return render_template("recipe.html", cocktail_id=cocktail_id)


# --- API: Ingredients ---

@app.route("/api/ingredients")
def get_ingredients():
    """Ingredients grouped by category for the bar page.
    Hides always-available categories and brand/specific ingredients."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT i.id, i.display_name, i.match_name, i.category_id,
                   c.name as category_name, c.sort_order,
                   CASE WHEN bs.id IS NOT NULL THEN 1 ELSE 0 END as in_stock
            FROM ingredients i
            LEFT JOIN categories c ON i.category_id = c.id
            LEFT JOIN bar_stock bs ON bs.ingredient_id = i.id
            WHERE i.always_available = 0
              AND i.general_id IS NULL
              AND (c.always_available = 0 OR c.always_available IS NULL)
            ORDER BY c.sort_order, c.name, i.display_name
        """).fetchall()

        categories = {}
        for row in rows:
            cat_id = row["category_id"] or 0
            cat_name = row["category_name"] or "Other"
            sort_order = row["sort_order"] or 999

            if cat_id not in categories:
                categories[cat_id] = {
                    "id": cat_id,
                    "name": cat_name,
                    "sort_order": sort_order,
                    "ingredients": [],
                }
            categories[cat_id]["ingredients"].append({
                "id": row["id"],
                "name": row["display_name"],
                "in_stock": bool(row["in_stock"]),
            })

        grouped = sorted(categories.values(), key=lambda c: c["sort_order"])

        stocked = conn.execute("SELECT COUNT(*) FROM bar_stock").fetchone()[0]

        return api_response(data={"categories": grouped, "stocked_count": stocked})
    finally:
        conn.close()


# --- API: Bar Stock ---

@app.route("/api/bar/stock", methods=["POST"])
def toggle_stock():
    """Toggle an ingredient in/out of stock."""
    body = request.get_json(silent=True) or {}
    ingredient_id = body.get("ingredient_id")
    stocked = body.get("stocked")

    if ingredient_id is None or stocked is None:
        return api_response(False, message="ingredient_id and stocked are required.", status_code=400)

    conn = get_db_connection()
    try:
        if stocked:
            conn.execute(
                "INSERT OR IGNORE INTO bar_stock (ingredient_id) VALUES (?)",
                (ingredient_id,),
            )
        else:
            conn.execute(
                "DELETE FROM bar_stock WHERE ingredient_id = ?",
                (ingredient_id,),
            )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM bar_stock").fetchone()[0]
        return api_response(data={"stocked_count": count})
    finally:
        conn.close()


# --- API: Shake ---

@app.route("/api/shake")
def shake():
    """Run matching algorithm, return results."""
    results = find_matches()
    return api_response(data=results)


# --- API: Recipe ---

@app.route("/api/recipe/<int:cocktail_id>")
def get_recipe(cocktail_id):
    """Full recipe with ingredients, stock status, rating, and notes."""
    conn = get_db_connection()
    try:
        cocktail = conn.execute(
            "SELECT id, name, primary_spirit, instructions, source_url FROM cocktails WHERE id = ?",
            (cocktail_id,),
        ).fetchone()

        if not cocktail:
            return api_response(False, message="Cocktail not found.", status_code=404)

        # Build stocked set: bar_stock + always_available
        stocked = set()
        for row in conn.execute("SELECT ingredient_id FROM bar_stock"):
            stocked.add(row["ingredient_id"])
        for row in conn.execute("SELECT id FROM ingredients WHERE always_available = 1"):
            stocked.add(row["id"])

        # General_id mapping: brand_id -> general_id
        general_map = {}
        for row in conn.execute("SELECT id, general_id FROM ingredients WHERE general_id IS NOT NULL"):
            general_map[row["id"]] = row["general_id"]

        subs = {}
        for row in conn.execute("SELECT ingredient_id, substitute_id FROM substitutes"):
            subs.setdefault(row["ingredient_id"], set()).add(row["substitute_id"])

        ing_rows = conn.execute("""
            SELECT ci.ingredient_id, ci.quantity, ci.unit, ci.sort_order,
                   i.display_name
            FROM cocktail_ingredients ci
            JOIN ingredients i ON i.id = ci.ingredient_id
            WHERE ci.cocktail_id = ?
            ORDER BY ci.sort_order
        """, (cocktail_id,)).fetchall()

        ingredients = []
        for row in ing_rows:
            iid = row["ingredient_id"]
            # Check stock: direct, via general_id, or via substitute
            if iid in stocked:
                status = "have"
            elif general_map.get(iid) and general_map[iid] in stocked:
                status = "have"
            elif _any_sub_stocked(iid, stocked, subs, general_map):
                status = "substitute"
            else:
                status = "missing"

            ingredients.append({
                "id": iid,
                "name": row["display_name"],
                "quantity": row["quantity"],
                "unit": row["unit"],
                "status": status,
            })

        # Ratings (composite)
        avg_row = conn.execute(
            "SELECT AVG(score) as avg, COUNT(*) as cnt FROM ratings WHERE cocktail_id = ?",
            (cocktail_id,),
        ).fetchone()
        avg_rating = round(avg_row["avg"], 1) if avg_row["avg"] else None
        rating_count = avg_row["cnt"]

        rating_rows = conn.execute(
            "SELECT id, score, comment, date_rated FROM ratings WHERE cocktail_id = ? ORDER BY date_rated DESC",
            (cocktail_id,),
        ).fetchall()
        ratings = [
            {"id": r["id"], "score": r["score"], "comment": r["comment"], "date": r["date_rated"]}
            for r in rating_rows
        ]

        # Notes
        note_rows = conn.execute(
            "SELECT id, note_text, date_created FROM notes WHERE cocktail_id = ? ORDER BY date_created DESC",
            (cocktail_id,),
        ).fetchall()
        notes = [
            {"id": n["id"], "text": n["note_text"], "date": n["date_created"]}
            for n in note_rows
        ]

        # Dismissed status
        is_dismissed = bool(conn.execute(
            "SELECT 1 FROM dismissed_cocktails WHERE cocktail_id = ?", (cocktail_id,)
        ).fetchone())

        return api_response(data={
            "id": cocktail["id"],
            "name": cocktail["name"],
            "primary_spirit": cocktail["primary_spirit"],
            "instructions": cocktail["instructions"],
            "source_url": cocktail["source_url"],
            "ingredients": ingredients,
            "avg_rating": avg_rating,
            "rating_count": rating_count,
            "ratings": ratings,
            "notes": notes,
            "is_dismissed": is_dismissed,
        })
    finally:
        conn.close()


def _any_sub_stocked(ingredient_id, stocked, subs, general_map):
    """Check if any substitute is stocked (directly or via general)."""
    sub_ids = subs.get(ingredient_id, set())
    for sid in sub_ids:
        if sid in stocked:
            return True
        gid = general_map.get(sid)
        if gid and gid in stocked:
            return True
    return False


# --- API: Rating ---

@app.route("/api/recipe/<int:cocktail_id>/rate", methods=["POST"])
def rate_cocktail(cocktail_id):
    """Rate a cocktail 1-5."""
    body = request.get_json(silent=True) or {}
    score = body.get("score")
    comment = (body.get("comment") or "").strip() or None

    if score is None or not (1 <= int(score) <= 5):
        return api_response(False, message="Score must be 1-5.", status_code=400)

    conn = get_db_connection()
    try:
        if not conn.execute("SELECT id FROM cocktails WHERE id = ?", (cocktail_id,)).fetchone():
            return api_response(False, message="Cocktail not found.", status_code=404)

        conn.execute(
            "INSERT INTO ratings (cocktail_id, score, comment) VALUES (?, ?, ?)",
            (cocktail_id, int(score), comment),
        )
        conn.commit()

        return api_response(data=_rating_summary(conn, cocktail_id), message="Rating saved.")
    finally:
        conn.close()


def _rating_summary(conn, cocktail_id):
    """Return avg_rating, rating_count, and ratings list for a cocktail."""
    avg_row = conn.execute(
        "SELECT AVG(score) as avg, COUNT(*) as cnt FROM ratings WHERE cocktail_id = ?",
        (cocktail_id,),
    ).fetchone()
    rating_rows = conn.execute(
        "SELECT id, score, comment, date_rated FROM ratings WHERE cocktail_id = ? ORDER BY date_rated DESC",
        (cocktail_id,),
    ).fetchall()
    return {
        "avg_rating": round(avg_row["avg"], 1) if avg_row["avg"] else None,
        "rating_count": avg_row["cnt"],
        "ratings": [
            {"id": r["id"], "score": r["score"], "comment": r["comment"], "date": r["date_rated"]}
            for r in rating_rows
        ],
    }


@app.route("/api/recipe/<int:cocktail_id>/rate/<int:rating_id>", methods=["DELETE"])
def delete_rating(cocktail_id, rating_id):
    """Delete a single rating."""
    conn = get_db_connection()
    try:
        result = conn.execute(
            "DELETE FROM ratings WHERE id = ? AND cocktail_id = ?",
            (rating_id, cocktail_id),
        )
        conn.commit()
        if result.rowcount == 0:
            return api_response(False, message="Rating not found.", status_code=404)
        return api_response(data=_rating_summary(conn, cocktail_id), message="Rating deleted.")
    finally:
        conn.close()


# --- API: Notes ---

@app.route("/api/recipe/<int:cocktail_id>/note", methods=["POST"])
def add_note(cocktail_id):
    """Add a note to a cocktail."""
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()

    if not text:
        return api_response(False, message="Note text is required.", status_code=400)

    conn = get_db_connection()
    try:
        if not conn.execute("SELECT id FROM cocktails WHERE id = ?", (cocktail_id,)).fetchone():
            return api_response(False, message="Cocktail not found.", status_code=404)

        cursor = conn.execute(
            "INSERT INTO notes (cocktail_id, note_text) VALUES (?, ?)",
            (cocktail_id, text),
        )
        conn.commit()

        return api_response(data={
            "id": cursor.lastrowid,
            "text": text,
            "date": None,
        }, message="Note added.")
    finally:
        conn.close()


@app.route("/api/recipe/<int:cocktail_id>/note/<int:note_id>", methods=["DELETE"])
def delete_note(cocktail_id, note_id):
    """Delete a note."""
    conn = get_db_connection()
    try:
        result = conn.execute(
            "DELETE FROM notes WHERE id = ? AND cocktail_id = ?",
            (note_id, cocktail_id),
        )
        conn.commit()
        if result.rowcount == 0:
            return api_response(False, message="Note not found.", status_code=404)
        return api_response(message="Note deleted.")
    finally:
        conn.close()


# --- API: Dismiss/Restore ---

@app.route("/api/recipe/<int:cocktail_id>/dismiss", methods=["POST"])
def dismiss_cocktail(cocktail_id):
    """Dismiss a cocktail from results."""
    conn = get_db_connection()
    try:
        if not conn.execute("SELECT id FROM cocktails WHERE id = ?", (cocktail_id,)).fetchone():
            return api_response(False, message="Cocktail not found.", status_code=404)
        conn.execute(
            "INSERT OR IGNORE INTO dismissed_cocktails (cocktail_id) VALUES (?)",
            (cocktail_id,),
        )
        conn.commit()
        return api_response(message="Cocktail dismissed.")
    finally:
        conn.close()


@app.route("/api/recipe/<int:cocktail_id>/restore", methods=["POST"])
def restore_cocktail(cocktail_id):
    """Restore a dismissed cocktail."""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM dismissed_cocktails WHERE cocktail_id = ?", (cocktail_id,))
        conn.commit()
        return api_response(message="Cocktail restored.")
    finally:
        conn.close()


@app.route("/api/dismissed")
def get_dismissed():
    """Return all dismissed cocktails with metadata."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT c.id, c.name, c.primary_spirit, dc.date_dismissed
            FROM dismissed_cocktails dc
            JOIN cocktails c ON c.id = dc.cocktail_id
            ORDER BY dc.date_dismissed DESC
        """).fetchall()
        dismissed = [
            {
                "id": r["id"],
                "name": r["name"],
                "primary_spirit": r["primary_spirit"],
                "date_dismissed": r["date_dismissed"],
            }
            for r in rows
        ]
        return api_response(data=dismissed)
    finally:
        conn.close()


# --- API: Sync ---

@app.route("/api/sync/cocktails", methods=["POST"])
def sync_cocktails():
    """Trigger a background sync with Kindred Cocktails."""
    with sync_lock:
        if sync_status["in_progress"]:
            return api_response(False, message="A sync is already in progress.", status_code=409)
        sync_status["in_progress"] = True
        sync_status["message"] = "Starting sync..."
        sync_status["current"] = 0
        sync_status["total"] = 0

    thread = threading.Thread(target=_run_sync, daemon=True)
    thread.start()
    return api_response(message="Sync started.")


@app.route("/api/sync/status")
def get_sync_status():
    return api_response(data={
        "in_progress": sync_status["in_progress"],
        "message": sync_status["message"],
        "current": sync_status["current"],
        "total": sync_status["total"],
    })


def _run_sync():
    """Run the Kindred Cocktails scraper in background."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scraper"))
    try:
        from scrape_kindred import run_scraper

        def progress_cb(message, current, total):
            sync_status["message"] = message
            sync_status["current"] = current
            sync_status["total"] = total

        results = run_scraper(progress_callback=progress_cb)
        sync_status["message"] = (
            f"Done! Added {results.get('added', 0)} new cocktails, "
            f"updated {results.get('updated', 0)}."
        )
    except ImportError:
        sync_status["message"] = "Scraper module not available. Run scrape_kindred.py manually."
    except Exception as e:
        sync_status["message"] = f"Error: {e}"
    finally:
        sync_status["in_progress"] = False


# --- App startup ---

if __name__ == "__main__":
    app.run(debug=True, port=3346)

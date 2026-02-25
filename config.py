import os

# Flask
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-fallback-key")

# Database
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "database", "bar_cart.db")

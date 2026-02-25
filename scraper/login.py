"""Authentication handler for Kindred Cocktails."""

import requests
from bs4 import BeautifulSoup

LOGIN_URL = "https://kindredcocktails.com/user/login"
BASE_URL = "https://kindredcocktails.com"


def create_session(username, password):
    """Create an authenticated requests session."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    # Get login page to find form tokens
    resp = session.get(LOGIN_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Find the login form and extract hidden fields
    form = soup.find("form", id="user-login-form") or soup.find("form")
    if not form:
        raise RuntimeError("Could not find login form")

    payload = {}
    # Collect all hidden inputs (CSRF tokens, form build IDs, etc.)
    for hidden in form.find_all("input", type="hidden"):
        name = hidden.get("name")
        value = hidden.get("value", "")
        if name:
            payload[name] = value

    # Add credentials
    payload["name"] = username
    payload["pass"] = password
    payload["op"] = "Log in"

    # Submit login
    action = form.get("action", LOGIN_URL)
    if action.startswith("/"):
        action = BASE_URL + action

    resp = session.post(action, data=payload)
    resp.raise_for_status()

    # Verify login succeeded - check for logout link or username on page
    if "log out" in resp.text.lower() or username.lower() in resp.text.lower():
        print("Login successful.")
        return session

    # Some Drupal sites redirect after login
    if resp.url != LOGIN_URL and "/user/login" not in resp.url:
        print("Login successful (redirected).")
        return session

    raise RuntimeError("Login failed — check credentials")

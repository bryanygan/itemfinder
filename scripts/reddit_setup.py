"""Interactive setup helper for Reddit API credentials.

Walks through getting Reddit API access and validates the connection.
Usage: python scripts/reddit_setup.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

SETUP_GUIDE = """
=== Reddit API Setup Guide ===

1. Go to: https://www.reddit.com/prefs/apps
2. Click "create another app..." at the bottom
3. Fill in:
   - Name: itemfinder (or anything)
   - Type: select "script"
   - Description: demand intelligence tool
   - About URL: (leave blank)
   - Redirect URI: http://localhost:8080
4. Click "create app"
5. Note down:
   - Client ID: the string under "personal use script" (below the app name)
   - Client Secret: the string next to "secret"

Rate limits:
  - Without account auth: 30 requests/minute
  - With account auth (username+password): 60 requests/minute
  - PRAW handles rate limiting automatically

Recommendation: Use "script" app type with username/password for 2x rate limit.
"""


def main():
    print(SETUP_GUIDE)

    client_id = input("Enter your Client ID: ").strip()
    client_secret = input("Enter your Client Secret: ").strip()
    user_agent = input("User Agent (press Enter for default): ").strip()
    username = input("Reddit Username (optional, press Enter to skip): ").strip()
    password = input("Reddit Password (optional, press Enter to skip): ").strip()

    if not user_agent:
        user_agent = "itemfinder/1.0 demand-intelligence"

    # Write .env file
    lines = [
        f"REDDIT_CLIENT_ID={client_id}",
        f"REDDIT_CLIENT_SECRET={client_secret}",
        f"REDDIT_USER_AGENT={user_agent}",
    ]
    if username:
        lines.append(f"REDDIT_USERNAME={username}")
    if password:
        lines.append(f"REDDIT_PASSWORD={password}")

    # Append to existing .env or create new
    mode = "a" if ENV_PATH.exists() else "w"
    with open(ENV_PATH, mode) as f:
        if mode == "a":
            f.write("\n# Reddit API credentials\n")
        f.write("\n".join(lines) + "\n")

    print(f"\nCredentials saved to {ENV_PATH}")

    # Test connection
    print("\nTesting connection...")
    os.environ["REDDIT_CLIENT_ID"] = client_id
    os.environ["REDDIT_CLIENT_SECRET"] = client_secret
    os.environ["REDDIT_USER_AGENT"] = user_agent
    if username:
        os.environ["REDDIT_USERNAME"] = username
    if password:
        os.environ["REDDIT_PASSWORD"] = password

    try:
        import praw
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            **({"username": username, "password": password} if username and password else {}),
        )
        # Test by fetching a subreddit
        sub = reddit.subreddit("FashionReps")
        print(f"  Connected! r/FashionReps has {sub.subscribers:,} subscribers")
        print(f"  Read-only mode: {reddit.read_only}")
        print("\nSetup complete! Run the ingestion with:")
        print("  python scripts/run_reddit.py")
        print("\nFor a quick test with one subreddit:")
        print("  python scripts/run_reddit.py --subreddits FashionReps --quick")
    except ImportError:
        print("  praw not installed. Run: pip install praw")
    except Exception as e:
        print(f"  Connection failed: {e}")
        print("  Check your credentials and try again.")


if __name__ == "__main__":
    main()

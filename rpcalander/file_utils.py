import json
import logging  # Edited by Taako
from datetime import datetime, timezone
from pathlib import Path

POST_TRACKER_PATH = Path(__file__).parent / \
                         "post_tracker.json"  # Edited by Taako

# Configure logging for debugging  # Edited by Taako
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)  # Edited by Taako


def read_last_posted():
    """Read the last posted timestamp from the JSON file."""  # Edited by Taako
    if not POST_TRACKER_PATH.exists():
        logging.debug(
            "post_tracker.json does not exist. Returning None.",
        )  # Edited by Taako
        return None

    with POST_TRACKER_PATH.open() as file:
        data = json.load(file)
        last_posted = data.get("last_posted")
        logging.debug(f"Read last_posted: {last_posted}")  # Edited by Taako
        return last_posted


def write_last_posted():
    """Write the current timestamp as the last posted time to the JSON file."""  # Edited by Taako
    now = datetime.now(timezone.utc).isoformat()  # Edited by Taako
    with POST_TRACKER_PATH.open("w") as file:
        json.dump({"last_posted": now}, file)  # Edited by Taako
    logging.debug(f"Wrote last_posted: {now}")  # Edited by Taako

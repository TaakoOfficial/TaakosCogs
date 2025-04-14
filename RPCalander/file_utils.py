import json
import logging  # Edited by Taako
from datetime import datetime
from pathlib import Path

POST_TRACKER_PATH = Path(__file__).parent / "post_tracker.json"  # Edited by Taako

# Configure logging for debugging  # Edited by Taako
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')  # Edited by Taako

def read_last_posted():
    """Read the last posted timestamp from the JSON file."""  # Edited by Taako
    if not POST_TRACKER_PATH.exists():
        logging.debug("post_tracker.json does not exist. Returning None.")  # Edited by Taako
        return None

    with open(POST_TRACKER_PATH, "r") as file:
        data = json.load(file)
        last_posted = data.get("last_posted")
        logging.debug(f"Read last_posted: {last_posted}")  # Edited by Taako
        return last_posted

def write_last_posted():
    """Write the current timestamp as the last posted time to the JSON file."""  # Edited by Taako
    now = datetime.now().isoformat()  # Edited by Taako
    with open(POST_TRACKER_PATH, "w") as file:
        json.dump({"last_posted": now}, file)  # Edited by Taako
    logging.debug(f"Wrote last_posted: {now}")  # Edited by Taako

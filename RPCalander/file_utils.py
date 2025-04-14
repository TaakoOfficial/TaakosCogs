import json
from datetime import datetime
from pathlib import Path

POST_TRACKER_PATH = Path(__file__).parent / "post_tracker.json"  # Edited by Taako

def read_last_posted():
    """Read the last posted timestamp from the JSON file."""  # Edited by Taako
    if not POST_TRACKER_PATH.exists():
        return None

    with open(POST_TRACKER_PATH, "r") as file:
        data = json.load(file)
        return data.get("last_posted")

def write_last_posted():
    """Write the current timestamp as the last posted time to the JSON file."""  # Edited by Taako
    now = datetime.now().isoformat()  # Edited by Taako
    with open(POST_TRACKER_PATH, "w") as file:
        json.dump({"last_posted": now}, file)  # Edited by Taako

import json
from datetime import datetime, timezone
from pathlib import Path

POST_TRACKER_PATH = Path(__file__).parent / \
                         "post_tracker.json"  # Edited by Taako


def read_last_posted():
    """Read the last posted timestamp from the JSON file."""  # Edited by Taako
    if not POST_TRACKER_PATH.exists():
        return None  # Edited by Taako

    with POST_TRACKER_PATH.open() as file:
        data = json.load(file)  # Edited by Taako
        return data.get("last_posted")  # Edited by Taako


def write_last_posted():
    """Write the current timestamp as the last posted time to the JSON file."""  # Edited by Taako
    now = datetime.now(timezone.utc).isoformat()  # Edited by Taako
    with POST_TRACKER_PATH.open("w") as file:
        json.dump({"last_posted": now}, file)  # Edited by Taako

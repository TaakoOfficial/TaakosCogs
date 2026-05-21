from typing import Optional, Dict, Any
import json

# Google API imports
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents"
]

# Helper to build Google Sheets service
def get_sheets_service(api_key: str) -> Any:
    creds = Credentials.from_service_account_info(json.loads(api_key), scopes=[SCOPES[0]])
    return build("sheets", "v4", credentials=creds)

# Helper to build Google Docs service
def get_docs_service(api_key: str) -> Any:
    creds = Credentials.from_service_account_info(json.loads(api_key), scopes=[SCOPES[1]])
    return build("docs", "v1", credentials=creds)

# Sheets: Export data to a sheet
def export_to_sheet(sheet_id: str, api_key: str, data: Dict[str, Any], range_: str = "A1") -> None:
    service = get_sheets_service(api_key)
    values = [[json.dumps(data, indent=2)]]
    body = {"values": values}
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_,
        valueInputOption="RAW",
        body=body
    ).execute()

# Sheets: Import data from a sheet
def import_from_sheet(sheet_id: str, api_key: str, range_: str = "A1") -> Optional[Dict[str, Any]]:
    service = get_sheets_service(api_key)
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_
    ).execute()
    values = result.get("values", [])
    if values and values[0]:
        try:
            return json.loads(values[0][0])
        except Exception:
            return None
    return None

def get_character_template(char_data: dict) -> str:
    """Generate a character template string for Google Doc export."""
    content = f"## {char_data.get('name', 'Unknown Character')}\n\n"
    
    if char_data.get('description'):
        content += f"{char_data['description']}\n\n"
    
    # Identity section
    identity = []
    if char_data.get('full_name'):
        identity.append(f"**Full Name:** {char_data['full_name']}")
    if char_data.get('species'):
        identity.append(f"**Species:** {char_data['species']}")
    if char_data.get('gender'):
        identity.append(f"**Gender:** {char_data['gender']}")
    
    if identity:
        content += "### Identity\n" + "\n".join(identity) + "\n\n"
    
    # Background
    if char_data.get('background'):
        content += f"### Background\n{char_data['background']}\n\n"
    
    # Traits
    if char_data.get('traits'):
        content += "### Traits\n" + "\n".join(f"• {t}" for t in char_data['traits']) + "\n\n"
    
    return content

def get_timeline_template(events) -> str:
    """Generate a timeline template string for Google Doc export."""
    content = ""
    for event in sorted(events, key=lambda e: e.get('created_at', '')):
        content += f"**{event.get('ic_date', 'Unknown Date')}**: {event.get('description', 'No description')}\n"
        if event.get('characters'):
            content += f"  *Characters: {', '.join(event['characters'])}*\n"
        content += "\n"
    return content

def export_to_doc(doc_id: str, api_key: str, data: dict):
    """Export Fable data to a Google Doc with proper formatting."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        import json
    except ImportError:
        raise ImportError("Required Google packages not found. Run [p]fable googlehelp for setup instructions.")

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(api_key),
        scopes=['https://www.googleapis.com/auth/documents']
    )
    service = build('docs', 'v1', credentials=credentials)

    # Start with a title
    content = "『 FABLE CHARACTER PROFILES 』\n\n"
    
    # Add each character with proper formatting
    if "characters" in data:
        for char_name, char_data in data["characters"].items():
            content += get_character_template(char_data)
            content += "\n\n" + "═" * 50 + "\n\n"  # Separator between characters

    # Add timeline if events exist
    if "events" in data and data["events"]:
        content += "\n\n『 CHARACTER TIMELINE 』\n\n"
        content += get_timeline_template(data["events"].values())

    # Update the document
    document = service.documents().get(documentId=doc_id).execute()
    service.documents().batchUpdate(
        documentId=doc_id,
        body={
            'requests': [
                {
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': len(document.get('body', {}).get('content', '')) - 1
                        }
                    }
                },
                {
                    'insertText': {
                        'location': {'index': 1},
                        'text': content
                    }
                }
            ]
        }
    ).execute()

# Docs: Import data from a doc (read all text)
def import_from_doc(doc_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    service = get_docs_service(api_key)
    doc = service.documents().get(documentId=doc_id).execute()
    text = ""
    for element in doc.get("body", {}).get("content", []):
        if "paragraph" in element:
            for elem in element["paragraph"].get("elements", []):
                if "textRun" in elem:
                    text += elem["textRun"].get("content", "")
    try:
        return json.loads(text)
    except Exception:
        return None

def import_to_sheet(sheet_id: str, api_key: str, data: Dict[str, Any], range_: str = "A1") -> None:
    """Import data to Google Sheet (alias for export_to_sheet for consistency)."""
    return export_to_sheet(sheet_id, api_key, data, range_)

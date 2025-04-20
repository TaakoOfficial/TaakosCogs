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

# Docs: Export data to a doc (overwrite entire doc)
def export_to_doc(doc_id: str, api_key: str, data: Dict[str, Any]) -> None:
    service = get_docs_service(api_key)
    # Clear the document
    requests = [
        {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": 1_000_000}}}
    ]
    service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    # Insert new content
    requests = [
        {"insertText": {"location": {"index": 1}, "text": json.dumps(data, indent=2)}}
    ]
    service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

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

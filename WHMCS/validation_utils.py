"""Validation utilities for WHMCS COG."""

import re
import logging
from typing import Optional, Dict, Any, Union

log = logging.getLogger("red.WHMCS.validation")


class ValidationError(Exception):
    """Exception raised for validation errors."""
    pass


def validate_client_id(client_id: Union[str, int]) -> int:
    """Validate and convert client ID.
    
    Args:
        client_id: The client ID to validate
        
    Returns:
        Validated client ID as integer
        
    Raises:
        ValidationError: If client ID is invalid
    """
    try:
        client_id_int = int(client_id)
        if client_id_int <= 0:
            raise ValidationError("Client ID must be a positive integer")
        return client_id_int
    except (ValueError, TypeError):
        raise ValidationError("Client ID must be a valid integer")


def validate_invoice_id(invoice_id: Union[str, int]) -> int:
    """Validate and convert invoice ID.
    
    Args:
        invoice_id: The invoice ID to validate
        
    Returns:
        Validated invoice ID as integer
        
    Raises:
        ValidationError: If invoice ID is invalid
    """
    try:
        invoice_id_int = int(invoice_id)
        if invoice_id_int <= 0:
            raise ValidationError("Invoice ID must be a positive integer")
        return invoice_id_int
    except (ValueError, TypeError):
        raise ValidationError("Invoice ID must be a valid integer")


def validate_ticket_id(ticket_id: Union[str, int]) -> int:
    """Validate and convert ticket ID.
    
    Args:
        ticket_id: The ticket ID to validate
        
    Returns:
        Validated ticket ID as integer
        
    Raises:
        ValidationError: If ticket ID is invalid
    """
    try:
        ticket_id_int = int(ticket_id)
        if ticket_id_int <= 0:
            raise ValidationError("Ticket ID must be a positive integer")
        return ticket_id_int
    except (ValueError, TypeError):
        raise ValidationError("Ticket ID must be a valid integer")


def validate_amount(amount: Union[str, float, int]) -> float:
    """Validate and convert monetary amount.
    
    Args:
        amount: The amount to validate
        
    Returns:
        Validated amount as float
        
    Raises:
        ValidationError: If amount is invalid
    """
    try:
        amount_float = float(amount)
        if amount_float < 0:
            raise ValidationError("Amount cannot be negative")
        if amount_float > 999999.99:
            raise ValidationError("Amount is too large (max: 999999.99)")
        # Round to 2 decimal places for currency
        return round(amount_float, 2)
    except (ValueError, TypeError):
        raise ValidationError("Amount must be a valid number")


def validate_email(email: str) -> str:
    """Validate email address format.
    
    Args:
        email: The email address to validate
        
    Returns:
        Validated email address
        
    Raises:
        ValidationError: If email is invalid
    """
    if not email or not isinstance(email, str):
        raise ValidationError("Email address is required")
    
    # Basic email regex pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        raise ValidationError("Invalid email address format")
    
    if len(email) > 254:  # RFC 5321 limit
        raise ValidationError("Email address is too long")
    
    return email.lower().strip()


def validate_url(url: str) -> str:
    """Validate WHMCS URL format.
    
    Args:
        url: The URL to validate
        
    Returns:
        Validated URL
        
    Raises:
        ValidationError: If URL is invalid
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL is required")
    
    url = url.strip()
    
    # Add https:// if no protocol specified
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Basic URL validation
    url_pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/.*)?$'
    
    if not re.match(url_pattern, url):
        raise ValidationError("Invalid URL format")
    
    # Remove trailing slash for consistency
    return url.rstrip('/')


def validate_api_identifier(identifier: str) -> str:
    """Validate API identifier format.
    
    Args:
        identifier: The API identifier to validate
        
    Returns:
        Validated identifier
        
    Raises:
        ValidationError: If identifier is invalid
    """
    if not identifier or not isinstance(identifier, str):
        raise ValidationError("API identifier is required")
    
    identifier = identifier.strip()
    
    # WHMCS API identifiers are typically 32 character alphanumeric strings
    if len(identifier) < 16:
        raise ValidationError("API identifier is too short")
    
    if len(identifier) > 64:
        raise ValidationError("API identifier is too long")
    
    # Check for valid characters (alphanumeric)
    if not re.match(r'^[a-zA-Z0-9]+$', identifier):
        raise ValidationError("API identifier contains invalid characters")
    
    return identifier


def validate_api_secret(secret: str) -> str:
    """Validate API secret format.
    
    Args:
        secret: The API secret to validate
        
    Returns:
        Validated secret
        
    Raises:
        ValidationError: If secret is invalid
    """
    if not secret or not isinstance(secret, str):
        raise ValidationError("API secret is required")
    
    secret = secret.strip()
    
    # WHMCS API secrets are typically 32 character alphanumeric strings
    if len(secret) < 16:
        raise ValidationError("API secret is too short")
    
    if len(secret) > 64:
        raise ValidationError("API secret is too long")
    
    # Check for valid characters (alphanumeric)
    if not re.match(r'^[a-zA-Z0-9]+$', secret):
        raise ValidationError("API secret contains invalid characters")
    
    return secret


def validate_search_term(search_term: str) -> str:
    """Validate search term.
    
    Args:
        search_term: The search term to validate
        
    Returns:
        Validated search term
        
    Raises:
        ValidationError: If search term is invalid
    """
    if not search_term or not isinstance(search_term, str):
        raise ValidationError("Search term is required")
    
    search_term = search_term.strip()
    
    if len(search_term) < 2:
        raise ValidationError("Search term must be at least 2 characters")
    
    if len(search_term) > 100:
        raise ValidationError("Search term is too long (max: 100 characters)")
    
    # Remove potentially dangerous characters
    forbidden_chars = ['<', '>', '"', "'", '&', '\x00']
    for char in forbidden_chars:
        if char in search_term:
            raise ValidationError(f"Search term contains forbidden character: {char}")
    
    return search_term


def validate_description(description: str) -> str:
    """Validate description text.
    
    Args:
        description: The description to validate
        
    Returns:
        Validated description
        
    Raises:
        ValidationError: If description is invalid
    """
    if not description or not isinstance(description, str):
        raise ValidationError("Description is required")
    
    description = description.strip()
    
    if len(description) < 5:
        raise ValidationError("Description must be at least 5 characters")
    
    if len(description) > 1000:
        raise ValidationError("Description is too long (max: 1000 characters)")
    
    return description


def validate_ticket_message(message: str) -> str:
    """Validate ticket message content.
    
    Args:
        message: The message to validate
        
    Returns:
        Validated message
        
    Raises:
        ValidationError: If message is invalid
    """
    if not message or not isinstance(message, str):
        raise ValidationError("Message is required")
    
    message = message.strip()
    
    if len(message) < 10:
        raise ValidationError("Message must be at least 10 characters")
    
    if len(message) > 5000:
        raise ValidationError("Message is too long (max: 5000 characters)")
    
    return message


def validate_page_number(page: Union[str, int]) -> int:
    """Validate page number for pagination.
    
    Args:
        page: The page number to validate
        
    Returns:
        Validated page number
        
    Raises:
        ValidationError: If page number is invalid
    """
    try:
        page_int = int(page)
        if page_int < 1:
            raise ValidationError("Page number must be 1 or greater")
        if page_int > 10000:  # Reasonable upper limit
            raise ValidationError("Page number is too large")
        return page_int
    except (ValueError, TypeError):
        raise ValidationError("Page number must be a valid integer")


def validate_limit(limit: Union[str, int]) -> int:
    """Validate limit parameter for API calls.
    
    Args:
        limit: The limit to validate
        
    Returns:
        Validated limit
        
    Raises:
        ValidationError: If limit is invalid
    """
    try:
        limit_int = int(limit)
        if limit_int < 1:
            raise ValidationError("Limit must be 1 or greater")
        if limit_int > 100:  # WHMCS API typically limits to 100
            raise ValidationError("Limit cannot exceed 100")
        return limit_int
    except (ValueError, TypeError):
        raise ValidationError("Limit must be a valid integer")


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks.
    
    Args:
        text: The text to sanitize
        
    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        return str(text)
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove control characters except newline and tab
    sanitized = ''
    for char in text:
        if ord(char) >= 32 or char in ['\n', '\t']:
            sanitized += char
    
    return sanitized.strip()


def validate_role_id(role_id: Union[str, int]) -> int:
    """Validate Discord role ID.
    
    Args:
        role_id: The role ID to validate
        
    Returns:
        Validated role ID
        
    Raises:
        ValidationError: If role ID is invalid
    """
    try:
        role_id_int = int(role_id)
        # Discord snowflake IDs are 64-bit integers
        if role_id_int < 1:
            raise ValidationError("Role ID must be a positive integer")
        if role_id_int > 2**63 - 1:
            raise ValidationError("Role ID is too large")
        return role_id_int
    except (ValueError, TypeError):
        raise ValidationError("Role ID must be a valid integer")


def validate_client_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate client data dictionary.
    
    Args:
        data: Dictionary containing client data
        
    Returns:
        Validated client data
        
    Raises:
        ValidationError: If client data is invalid
    """
    validated = {}
    
    # Required fields
    required_fields = ['firstname', 'lastname', 'email']
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValidationError(f"Required field '{field}' is missing")
    
    # Validate email
    validated['email'] = validate_email(data['email'])
    
    # Validate names
    for name_field in ['firstname', 'lastname']:
        name = str(data[name_field]).strip()
        if len(name) < 1:
            raise ValidationError(f"{name_field} cannot be empty")
        if len(name) > 50:
            raise ValidationError(f"{name_field} is too long (max: 50 characters)")
        # Check for potentially dangerous characters
        if re.search(r'[<>"\']', name):
            raise ValidationError(f"{name_field} contains invalid characters")
        validated[name_field] = name
    
    # Optional fields with validation
    optional_fields = {
        'companyname': 100,
        'address1': 100,
        'address2': 100,
        'city': 50,
        'state': 50,
        'postcode': 20,
        'country': 2,
        'phonenumber': 20
    }
    
    for field, max_length in optional_fields.items():
        if field in data and data[field]:
            value = str(data[field]).strip()
            if len(value) > max_length:
                raise ValidationError(f"{field} is too long (max: {max_length} characters)")
            validated[field] = sanitize_input(value)
    
    return validated
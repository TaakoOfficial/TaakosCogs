"""WHMCS API client wrapper for async operations."""

import aiohttp
import asyncio
import hashlib
import logging
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin

log = logging.getLogger("red.WHMCS.api")


class WHMCSAPIError(Exception):
    """Base exception for WHMCS API errors."""
    pass


class WHMCSAuthenticationError(WHMCSAPIError):
    """Raised when authentication fails."""
    pass


class WHMCSRateLimitError(WHMCSAPIError):
    """Raised when rate limit is exceeded."""
    pass


class WHMCSAPIClient:
    """Async WHMCS API client wrapper.
    
    This class provides an async interface to the WHMCS API,
    handling authentication, rate limiting, and error management.
    """
    
    def __init__(self, base_url: str, timeout: int = 30):
        """Initialize the WHMCS API client.
        
        Args:
            base_url: The base URL of the WHMCS installation
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_url = urljoin(self.base_url, '/includes/api.php')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Authentication credentials
        self.identifier: Optional[str] = None
        self.secret: Optional[str] = None
        self.access_key: Optional[str] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        
        # Rate limiting
        self.rate_limit = 60  # requests per minute
        self.request_timestamps: List[float] = []
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def set_api_credentials(self, identifier: str, secret: str, access_key: Optional[str] = None):
        """Set API credentials for authentication.
        
        Args:
            identifier: API identifier from WHMCS
            secret: API secret from WHMCS
            access_key: Optional access key to bypass IP restrictions
        """
        self.identifier = identifier
        self.secret = secret
        self.access_key = access_key
    
    def set_admin_credentials(self, username: str, password: str, access_key: Optional[str] = None):
        """Set admin credentials for authentication.
        
        Args:
            username: Admin username
            password: Admin password (will be MD5 hashed)
            access_key: Optional access key to bypass IP restrictions
        """
        self.username = username
        self.password = hashlib.md5(password.encode()).hexdigest()
        self.access_key = access_key
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        now = asyncio.get_event_loop().time()
        
        # Remove timestamps older than 1 minute
        cutoff = now - 60
        self.request_timestamps = [ts for ts in self.request_timestamps if ts > cutoff]
        
        # Check if we're at the rate limit
        if len(self.request_timestamps) >= self.rate_limit:
            sleep_time = 60 - (now - self.request_timestamps[0])
            if sleep_time > 0:
                log.warning(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
        
        self.request_timestamps.append(now)
    
    def _build_request_data(self, action: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build request data for API call.
        
        Args:
            action: The WHMCS API action to perform
            parameters: Additional parameters for the API call
            
        Returns:
            Dictionary containing the request data
        """
        data = {
            'action': action,
            'responsetype': 'json'
        }
        
        # Add authentication
        if self.identifier and self.secret:
            data['identifier'] = self.identifier
            data['secret'] = self.secret
        elif self.username and self.password:
            data['username'] = self.username
            data['password'] = self.password
        else:
            raise WHMCSAuthenticationError("No authentication credentials provided")
        
        # Add access key if provided
        if self.access_key:
            data['accesskey'] = self.access_key
        
        # Add additional parameters
        if parameters:
            data.update(parameters)
        
        return data
    
    async def _make_request(self, action: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an API request to WHMCS.
        
        Args:
            action: The WHMCS API action to perform
            parameters: Additional parameters for the API call
            
        Returns:
            The API response as a dictionary
            
        Raises:
            WHMCSAPIError: If the API request fails
            WHMCSAuthenticationError: If authentication fails
            WHMCSRateLimitError: If rate limit is exceeded
        """
        if not self.session:
            raise WHMCSAPIError("Session not initialized. Use async context manager.")
        
        await self._check_rate_limit()
        
        data = self._build_request_data(action, parameters)
        
        try:
            async with self.session.post(self.api_url, data=data) as response:
                response_data = await response.json()
                
                # Check for API errors
                if response_data.get('result') == 'error':
                    error_msg = response_data.get('message', 'Unknown API error')
                    
                    # Handle specific error types
                    if 'authentication' in error_msg.lower():
                        raise WHMCSAuthenticationError(error_msg)
                    elif 'rate limit' in error_msg.lower():
                        raise WHMCSRateLimitError(error_msg)
                    else:
                        raise WHMCSAPIError(error_msg)
                
                return response_data
                
        except aiohttp.ClientError as e:
            raise WHMCSAPIError(f"HTTP request failed: {e}")
        except Exception as e:
            raise WHMCSAPIError(f"Unexpected error: {e}")
    
    # Client Management Methods
    async def get_clients(self, limit: int = 25, offset: int = 0, search: Optional[str] = None) -> Dict[str, Any]:
        """Get a list of clients.
        
        Args:
            limit: Number of clients to return (max 100)
            offset: Offset for pagination
            search: Search term to filter clients
            
        Returns:
            Dictionary containing client data
        """
        parameters = {
            'limitstart': str(offset),
            'limitnum': str(min(limit, 100))
        }
        
        if search:
            parameters['search'] = search
        
        return await self._make_request('GetClients', parameters)
    
    async def get_client(self, client_id: int) -> Dict[str, Any]:
        """Get details for a specific client.
        
        Args:
            client_id: The client ID to retrieve
            
        Returns:
            Dictionary containing client details
        """
        parameters = {'clientid': str(client_id)}
        return await self._make_request('GetClientsDetails', parameters)
    
    async def add_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new client.
        
        Args:
            client_data: Dictionary containing client information
            
        Returns:
            Dictionary containing the new client ID
        """
        return await self._make_request('AddClient', client_data)
    
    async def update_client(self, client_id: int, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing client.
        
        Args:
            client_id: The client ID to update
            client_data: Dictionary containing updated client information
            
        Returns:
            Dictionary containing update result
        """
        parameters = {'clientid': str(client_id)}
        parameters.update(client_data)
        return await self._make_request('UpdateClient', parameters)
    
    # Billing Methods
    async def get_invoices(self, client_id: Optional[int] = None, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        """Get invoices.
        
        Args:
            client_id: Optional client ID to filter invoices
            limit: Number of invoices to return
            offset: Offset for pagination
            
        Returns:
            Dictionary containing invoice data
        """
        parameters = {
            'limitstart': str(offset),
            'limitnum': str(min(limit, 100))
        }
        
        if client_id:
            parameters['userid'] = str(client_id)
        
        return await self._make_request('GetInvoices', parameters)
    
    async def get_invoice(self, invoice_id: int) -> Dict[str, Any]:
        """Get details for a specific invoice.
        
        Args:
            invoice_id: The invoice ID to retrieve
            
        Returns:
            Dictionary containing invoice details
        """
        parameters = {'invoiceid': str(invoice_id)}
        return await self._make_request('GetInvoice', parameters)
    
    async def add_credit(self, client_id: int, amount: float, description: str) -> Dict[str, Any]:
        """Add credit to a client account.
        
        Args:
            client_id: The client ID
            amount: Credit amount to add
            description: Description for the credit
            
        Returns:
            Dictionary containing the result
        """
        parameters = {
            'clientid': str(client_id),
            'amount': str(amount),
            'description': description
        }
        return await self._make_request('AddCredit', parameters)
    
    # Support Methods
    async def get_tickets(self, client_id: Optional[int] = None, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        """Get support tickets.
        
        Args:
            client_id: Optional client ID to filter tickets
            limit: Number of tickets to return
            offset: Offset for pagination
            
        Returns:
            Dictionary containing ticket data
        """
        parameters = {
            'limitstart': str(offset),
            'limitnum': str(min(limit, 100))
        }
        
        if client_id:
            parameters['clientid'] = str(client_id)
        
        return await self._make_request('GetTickets', parameters)
    
    async def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """Get details for a specific ticket, trying all possible ID fields.
        Args:
            ticket_id: The ticket ID to retrieve (numeric, alphanumeric, or mask)
        Returns:
            Dictionary containing ticket details or empty dict if not found
        """
        clean_ticket_id = ticket_id.lstrip('#').strip()
        log.info(f"WHMCS API: Looking up ticket {clean_ticket_id}")

        tried = []
        # Try all possible ID fields in order: ticketid, ticketnum, tid, maskid
        id_fields = [
            ("ticketid", clean_ticket_id if clean_ticket_id.isdigit() else None),
            ("ticketnum", clean_ticket_id),
            ("tid", clean_ticket_id),
            ("maskid", clean_ticket_id),
        ]
        for field, value in id_fields:
            if not value:
                continue
            try:
                log.info(f"WHMCS API: Trying GetTicket with {field}={value}")
                resp = await self._make_request('GetTicket', {field: value})
                log.info(f"WHMCS API: GetTicket {field} response: {resp}")
                tried.append((field, value, resp.get("result"), resp.get("ticket", None)))
                if resp.get("result") == "success" and resp.get("ticket"):
                    log.info(f"WHMCS API: Found ticket using {field}={value}")
                    return resp
            except Exception as e:
                log.warning(f"WHMCS API: GetTicket with {field}={value} failed: {e}")
        log.warning(f"WHMCS API: Ticket {clean_ticket_id} not found after trying all ID fields. Tried: {tried}")
        return {}
    
    async def add_ticket_reply(self, ticket_id: str, message: str, admin_username: Optional[str] = None, id_field: Optional[str] = None) -> Dict[str, Any]:
        """Add a reply to a support ticket.

        Args:
            ticket_id: The ticket ID value (string)
            message: Reply message
            admin_username: Optional admin username for the reply
            id_field: The WHMCS ticket field to use (should be 'ticketid' - the internal numeric ID)

        Returns:
            Dictionary containing the result
        """
        parameters = {
            'message': message
        }
        if admin_username:
            parameters['adminusername'] = admin_username

        # Clean up ticket ID - remove # prefix if present
        clean_ticket_id = ticket_id.lstrip('#').strip()
        log.info(f"WHMCS API: Adding reply to ticket {clean_ticket_id}")

        # According to WHMCS API docs, AddTicketReply requires 'ticketid' (internal numeric ID)
        # Not ticketnum, tid, or maskid. We must use the internal database ID.
        if id_field and id_field == 'ticketid':
            # Use provided ticketid directly
            parameters['ticketid'] = clean_ticket_id
            log.info(f"WHMCS API: Using provided ticketid field: {clean_ticket_id}")
        elif clean_ticket_id.isdigit():
            # If clean_ticket_id is numeric, assume it's the internal ticketid
            parameters['ticketid'] = clean_ticket_id
            log.info(f"WHMCS API: Using numeric ticket_id as ticketid: {clean_ticket_id}")
        else:
            # If not numeric, we need to look up the internal ticketid first
            # This is the correct approach according to WHMCS API documentation
            try:
                log.info(f"WHMCS API: Looking up ticket {clean_ticket_id} to get internal ID")
                ticket_resp = await self.get_ticket(clean_ticket_id)
                if ticket_resp.get("ticket"):
                    internal_id = ticket_resp["ticket"].get("id") or ticket_resp["ticket"].get("ticketid")
                    if internal_id:
                        parameters['ticketid'] = str(internal_id)
                        log.info(f"WHMCS API: Resolved ticket ID {clean_ticket_id} to internal ID {internal_id}")
                    else:
                        log.error(f"WHMCS API: Could not find internal ticket ID for {clean_ticket_id}")
                        return {"result": "error", "message": f"Could not find internal ticket ID for {clean_ticket_id}"}
                else:
                    log.error(f"WHMCS API: Ticket {clean_ticket_id} not found")
                    return {"result": "error", "message": f"Ticket {clean_ticket_id} not found"}
            except Exception as e:
                log.error(f"WHMCS API: Failed to lookup ticket {clean_ticket_id}: {e}")
                return {"result": "error", "message": f"Failed to lookup ticket {clean_ticket_id}: {e}"}

        try:
            log.info(f"WHMCS API: Calling AddTicketReply with parameters: {parameters}")
            resp = await self._make_request('AddTicketReply', parameters)
            log.info(f"WHMCS API: AddTicketReply response: {resp}")
            return resp
        except Exception as e:
            log.error(f"WHMCS API: AddTicketReply failed with parameters {parameters}: {e}")
            return {"result": "error", "message": f"AddTicketReply failed: {e}"}
    
    # System Methods
    async def test_connection(self) -> Dict[str, Any]:
        """Test the API connection.
        
        Returns:
            Dictionary containing system details if connection successful
        """
        return await self._make_request('WhmcsDetails')
    
    async def get_admin_details(self) -> Dict[str, Any]:
        """Get admin user details.
        
        Returns:
            Dictionary containing admin details
        """
        return await self._make_request('GetAdminDetails')
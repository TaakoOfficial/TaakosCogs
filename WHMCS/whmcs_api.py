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
            'limitstart': offset,
            'limitnum': min(limit, 100)
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
        parameters = {'clientid': client_id}
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
        parameters = {'clientid': client_id}
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
            'limitstart': offset,
            'limitnum': min(limit, 100)
        }
        
        if client_id:
            parameters['userid'] = client_id
        
        return await self._make_request('GetInvoices', parameters)
    
    async def get_invoice(self, invoice_id: int) -> Dict[str, Any]:
        """Get details for a specific invoice.
        
        Args:
            invoice_id: The invoice ID to retrieve
            
        Returns:
            Dictionary containing invoice details
        """
        parameters = {'invoiceid': invoice_id}
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
            'clientid': client_id,
            'amount': amount,
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
            'limitstart': offset,
            'limitnum': min(limit, 100)
        }
        
        if client_id:
            parameters['clientid'] = client_id
        
        return await self._make_request('GetTickets', parameters)
    
    async def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """Get details for a specific ticket.
        
        Args:
            ticket_id: The ticket ID to retrieve (can be numeric, alphanumeric like GLY-907775, or with # prefix like #WYI-894412)
            
        Returns:
            Dictionary containing ticket details
        """
        # Clean up ticket ID - remove # prefix if present
        clean_ticket_id = ticket_id.lstrip('#').strip()

        # Try ticketid if numeric, else ticketnum (per WHMCS API docs)
        if clean_ticket_id.isdigit():
            try:
                resp = await self._make_request('GetTicket', {'ticketid': clean_ticket_id})
                if resp.get("ticket"):
                    return resp
            except Exception:
                pass
        # Always try ticketnum as fallback (for alphanumeric or if numeric fails)
        try:
            resp = await self._make_request('GetTicket', {'ticketnum': clean_ticket_id})
            if resp.get("ticket"):
                return resp
        except Exception:
            pass
        # If all fail, return empty dict (not found)
        return {}
    
    async def add_ticket_reply(self, ticket_id: str, message: str, admin_username: Optional[str] = None) -> Dict[str, Any]:
        """Add a reply to a support ticket.
        
        Args:
            ticket_id: The ticket ID (can be numeric, alphanumeric like GLY-907775, or with # prefix like #WYI-894412)
            message: Reply message
            admin_username: Optional admin username for the reply
            
        Returns:
            Dictionary containing the result
        """
        parameters = {
            'message': message
        }
        
        # Clean up ticket ID - remove # prefix if present
        clean_ticket_id = ticket_id.lstrip('#').strip()
        
        # Try ticketid if numeric, else ticketnum (per WHMCS API docs)
        if clean_ticket_id.isdigit():
            parameters['ticketid'] = clean_ticket_id
            if admin_username:
                parameters['adminusername'] = admin_username
            try:
                resp = await self._make_request('AddTicketReply', parameters)
                if resp.get("result") == "success":
                    return resp
            except Exception:
                pass
            # If numeric fails, try as ticketnum as fallback (rare, but for edge cases)
            parameters.pop('ticketid', None)
        parameters['ticketnum'] = clean_ticket_id
        if admin_username:
            parameters['adminusername'] = admin_username
        try:
            resp = await self._make_request('AddTicketReply', parameters)
            if resp.get("result") == "success":
                return resp
        except Exception:
            pass
        return {"result": "error", "message": "Failed to add reply with either ticketid or ticketnum"}
    
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
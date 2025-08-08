import typing

def setup_dashboard_pages(cog):
    """Setup dashboard pages for the YALC cog and bind them to the cog instance."""
    
    # Get the dashboard_page decorator from the module where it's defined
    import sys
    dashboard_page = None
    
    # Find the dashboard_page decorator in the YALC module
    if hasattr(sys.modules.get('YALC.yalc'), 'dashboard_page'):
        dashboard_page = sys.modules['YALC.yalc'].dashboard_page
    elif hasattr(cog, 'dashboard_page'):
        dashboard_page = cog.dashboard_page
    else:
        # Create a simple decorator if not found
        def dashboard_page(*args, **kwargs):
            def decorator(func):
                func.__dashboard_decorator_params__ = (args, kwargs)
                return func
            return decorator
    
    @dashboard_page(name=None, description="YALC Dashboard Home", methods=("GET",), is_owner=False)
    async def dashboard_home(self, user, **kwargs) -> typing.Dict[str, typing.Any]:
        """Dashboard home page for YALC."""
        try:
            source = '''
            <div class="container mt-4">
                <div class="row">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header">
                                <h2><i class="fas fa-clipboard-list"></i> Welcome to YALC Dashboard</h2>
                            </div>
                            <div class="card-body">
                                <p class="lead">Yet Another Logging Cog - Comprehensive Discord event logging with dashboard integration</p>
                                <div class="row">
                                    <div class="col-md-6">
                                        <h4>Features:</h4>
                                        <ul class="list-group list-group-flush">
                                            <li class="list-group-item">🗑️ Message deletion tracking</li>
                                            <li class="list-group-item">✏️ Message edit logging</li>
                                            <li class="list-group-item">👋 Member join/leave events</li>
                                            <li class="list-group-item">🔨 Moderation action logging</li>
                                            <li class="list-group-item">📝 Channel management events</li>
                                            <li class="list-group-item">⚙️ Server configuration changes</li>
                                        </ul>
                                    </div>
                                    <div class="col-md-6">
                                        <h4>Quick Actions:</h4>
                                        <a href="settings" class="btn btn-primary btn-block mb-2">
                                            <i class="fas fa-cog"></i> Configure Settings
                                        </a>
                                        <a href="about" class="btn btn-info btn-block mb-2">
                                            <i class="fas fa-info-circle"></i> About YALC
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            '''
            
            return {
                "status": 0,
                "web_content": {"source": source},
            }
        except Exception as e:
            return {
                "status": 1,
                "error_title": "Dashboard Error",
                "error_message": f"Failed to load YALC dashboard home: {e}"
            }

    @dashboard_page(name="settings", description="Configure YALC logging settings", methods=("GET",), is_owner=False)
    async def dashboard_settings(self, user, guild, request: typing.Optional[dict] = None, **kwargs) -> typing.Dict[str, typing.Any]:
        """Dashboard settings page for YALC."""
        try:
            
            
            if not guild:
                return {
                    "status": 1,
                    "error_title": "Guild Required",
                    "error_message": "This page requires a guild context."
                }
                
            config = cog.config.guild(guild)
            settings = await config.all()
            success_message = ""
            error_message = ""
            
            # Check for success message from redirect
            if kwargs.get('saved') == '1':
                success_message = "Configuration updated successfully!"
            
            # Count enabled events
            enabled_events = sum(1 for enabled in settings["events"].values() if enabled)
            total_events = len(settings["events"])
            
            # Get configured channels
            configured_channels = sum(1 for channel_id in settings["event_channels"].values() if channel_id)
            
            # Get ignore counts
            ignored_users = len(settings.get("ignored_users", []))
            ignored_roles = len(settings.get("ignored_roles", []))
            ignored_channels = len(settings.get("ignored_channels", []))
            
            # Build channel options
            channel_options = ""
            for channel in guild.text_channels:
                channel_options += f'<option value="{channel.id}">#{channel.name}</option>'
            
            # Build event configuration form
            event_form = ""
            categories = {
                "Message Events": [k for k in cog.event_descriptions.keys() if k.startswith("message_")],
                "Member Events": [k for k in cog.event_descriptions.keys() if k.startswith("member_")],
                "Channel Events": [k for k in cog.event_descriptions.keys() if k.startswith(("channel_", "thread_", "forum_"))],
                "Role Events": [k for k in cog.event_descriptions.keys() if k.startswith("role_")],
                "Guild Events": [k for k in cog.event_descriptions.keys() if k.startswith(("guild_", "emoji_", "sticker_"))],
                "Other Events": [k for k in cog.event_descriptions.keys() if not any(k.startswith(p) for p in
                                ["message_", "member_", "channel_", "thread_", "forum_", "role_", "guild_", "emoji_", "sticker_"])]
            }
            
            for category, events in categories.items():
                if events:
                    event_form += f'<h6 class="mt-3">{category}</h6>'
                    for event in events:
                        emoji, description = cog.event_descriptions[event]
                        enabled = settings["events"].get(event, False)
                        channel_id = settings["event_channels"].get(event, None)
                        
                        event_form += f'''
                        <div class="row mb-2">
                            <div class="col-md-1">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" name="events" value="{event}"
                                           id="event_{event}" {"checked" if enabled else ""}>
                                </div>
                            </div>
                            <div class="col-md-5">
                                <label class="form-check-label" for="event_{event}">
                                    {emoji} {description}
                                </label>
                            </div>
                            <div class="col-md-6">
                                <select class="form-select form-select-sm" name="event_channels[{event}]">
                                    <option value="">Select Channel...</option>
                                    {channel_options}
                                </select>
                            </div>
                        </div>
                        '''
                        
                        # Set selected channel
                        if channel_id:
                            event_form = event_form.replace(f'value="{channel_id}"', f'value="{channel_id}" selected')
            
            
            
            # Build messages
            messages = ""
            if success_message:
                messages += f'<div class="alert alert-success alert-dismissible fade show" role="alert">{success_message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>'
            if error_message:
                messages += f'<div class="alert alert-danger alert-dismissible fade show" role="alert">{error_message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>'
            
            source = f'''
            <div class="container mt-4">
                {messages}
                <div class="row">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header">
                                <h3><i class="fas fa-cog"></i> YALC Configuration for {guild.name}</h3>
                            </div>
                            <div class="card-body">
                                <form method="post" action="settings_save">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5>Event Configuration</h5>
                                                </div>
                                                <div class="card-body">
                                                    <p><strong>Enabled Events:</strong> {enabled_events} / {total_events}</p>
                                                    <p><strong>Configured Channels:</strong> {configured_channels}</p>
                                                    <div class="progress mb-3">
                                                        <div class="progress-bar" role="progressbar"
                                                             style="width: {(enabled_events/total_events*100):.1f}%">
                                                            {(enabled_events/total_events*100):.1f}%
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5>General Settings</h5>
                                                </div>
                                                <div class="card-body">
                                                    <div class="form-check mb-2">
                                                        <input class="form-check-input" type="checkbox" name="ignore_bots" value="true"
                                                               id="ignore_bots" {"checked" if settings.get("ignore_bots", False) else ""}>
                                                        <label class="form-check-label" for="ignore_bots">
                                                            Ignore Bot Messages
                                                        </label>
                                                    </div>
                                                    <div class="form-check mb-2">
                                                        <input class="form-check-input" type="checkbox" name="ignore_webhooks" value="true"
                                                               id="ignore_webhooks" {"checked" if settings.get("ignore_webhooks", False) else ""}>
                                                        <label class="form-check-label" for="ignore_webhooks">
                                                            Ignore Webhook Messages
                                                        </label>
                                                    </div>
                                                    <div class="form-check mb-2">
                                                        <input class="form-check-input" type="checkbox" name="ignore_tupperbox" value="true"
                                                               id="ignore_tupperbox" {"checked" if settings.get("ignore_tupperbox", True) else ""}>
                                                        <label class="form-check-label" for="ignore_tupperbox">
                                                            Ignore Tupperbox Messages
                                                        </label>
                                                    </div>
                                                    <div class="form-check mb-2">
                                                        <input class="form-check-input" type="checkbox" name="ignore_apps" value="true"
                                                               id="ignore_apps" {"checked" if settings.get("ignore_apps", True) else ""}>
                                                        <label class="form-check-label" for="ignore_apps">
                                                            Ignore Application Messages
                                                        </label>
                                                    </div>
                                                    <div class="form-check mb-2">
                                                        <input class="form-check-input" type="checkbox" name="include_thumbnails" value="true"
                                                               id="include_thumbnails" {"checked" if settings.get("include_thumbnails", True) else ""}>
                                                        <label class="form-check-label" for="include_thumbnails">
                                                            Include User Thumbnails
                                                        </label>
                                                    </div>
                                                    <div class="form-check mb-2">
                                                        <input class="form-check-input" type="checkbox" name="detect_proxy_deletes" value="true"
                                                               id="detect_proxy_deletes" {"checked" if settings.get("detect_proxy_deletes", True) else ""}>
                                                        <label class="form-check-label" for="detect_proxy_deletes">
                                                            Detect Proxy Deletes
                                                        </label>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div class="row mt-4">
                                        <div class="col-md-12">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5>Advanced Settings</h5>
                                                </div>
                                                <div class="card-body">
                                                    <div class="row">
                                                        <div class="col-md-6">
                                                            <div class="mb-3">
                                                                <label for="tupperbox_ids" class="form-label">Tupperbox Bot IDs (comma-separated)</label>
                                                                <input type="text" class="form-control" id="tupperbox_ids" name="tupperbox_ids"
                                                                       value="{','.join(settings.get('tupperbox_ids', []))}"
                                                                       placeholder="239232811662311425">
                                                            </div>
                                                            <div class="mb-3">
                                                                <label for="message_prefix_filter" class="form-label">Message Prefix Filters (comma-separated)</label>
                                                                <input type="text" class="form-control" id="message_prefix_filter" name="message_prefix_filter"
                                                                       value="{','.join(settings.get('message_prefix_filter', []))}"
                                                                       placeholder="!,;,//,pk;">
                                                            </div>
                                                        </div>
                                                        <div class="col-md-6">
                                                            <div class="mb-3">
                                                                <label for="webhook_name_filter" class="form-label">Webhook Name Filters (comma-separated)</label>
                                                                <input type="text" class="form-control" id="webhook_name_filter" name="webhook_name_filter"
                                                                       value="{','.join(settings.get('webhook_name_filter', []))}"
                                                                       placeholder="tupperbox,carl">
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div class="row mt-4">
                                        <div class="col-md-12">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5>Event Configuration</h5>
                                                </div>
                                                <div class="card-body">
                                                    <div class="row">
                                                        <div class="col-md-1"><strong>Enable</strong></div>
                                                        <div class="col-md-5"><strong>Event Type</strong></div>
                                                        <div class="col-md-6"><strong>Log Channel</strong></div>
                                                    </div>
                                                    <hr>
                                                    {event_form}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div class="row mt-4">
                                        <div class="col-md-12">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5>Current Ignore Lists</h5>
                                                </div>
                                                <div class="card-body">
                                                    <div class="row">
                                                        <div class="col-md-4">
                                                            <p><strong>Ignored Users:</strong> {ignored_users}</p>
                                                        </div>
                                                        <div class="col-md-4">
                                                            <p><strong>Ignored Roles:</strong> {ignored_roles}</p>
                                                        </div>
                                                        <div class="col-md-4">
                                                            <p><strong>Ignored Channels:</strong> {ignored_channels}</p>
                                                        </div>
                                                    </div>
                                                    <div class="alert alert-info">
                                                        <strong>Note:</strong> Use Discord commands to manage ignore lists:
                                                        <code>/yalc ignore user</code>, <code>/yalc ignore role</code>, <code>/yalc ignore channel</code>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div class="row mt-4">
                                        <div class="col-md-12 text-center">
                                            <button type="submit" class="btn btn-primary btn-lg">
                                                <i class="fas fa-save"></i> Save Configuration
                                            </button>
                                        </div>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            '''
            
            return {
                "status": 0,
                "web_content": {"source": source},
                "csrf_token": await self._generate_csrf_token(user, guild)
            }
        except Exception as e:
            return {
                "status": 1,
                "error_title": "Settings Error",
                "error_message": f"Failed to load YALC settings: {e}"
            }

    @dashboard_page(name="settings_save", description="Save YALC settings", methods=("POST",), is_owner=False)
    async def dashboard_settings_save(self, user, guild, request: typing.Optional[dict] = None, **kwargs) -> typing.Dict[str, typing.Any]:
        """Handle settings form submission."""
        try:
            if not guild:
                return {
                    "status": 1,
                    "error_title": "Guild Required",
                    "error_message": "This page requires a guild context."
                }
            
            # Validate CSRF token
            if not await self._validate_csrf_token(user, guild, request):
                return {
                    "status": 1,
                    "error_title": "CSRF Validation Failed",
                    "error_message": "Invalid or missing CSRF token. Please try again."
                }
                
            config = cog.config.guild(guild)
            
            if request and request.get('method') == 'POST':
                try:
                    form_data = request.get('form', {})
                    
                    # Update event enablement
                    if 'events' in form_data:
                        async with config.events() as events:
                            for event_type in cog.event_descriptions.keys():
                                events[event_type] = event_type in form_data['events']
                    
                    # Update event channels
                    if 'event_channels' in form_data:
                        async with config.event_channels() as event_channels:
                            for event_type, channel_id in form_data['event_channels'].items():
                                if channel_id and channel_id.isdigit():
                                    event_channels[event_type] = int(channel_id)
                                else:
                                    event_channels[event_type] = None
                    
                    # Update general settings
                    if 'ignore_bots' in form_data:
                        await config.ignore_bots.set(form_data['ignore_bots'] == 'true')
                    if 'ignore_webhooks' in form_data:
                        await config.ignore_webhooks.set(form_data['ignore_webhooks'] == 'true')
                    if 'ignore_tupperbox' in form_data:
                        await config.ignore_tupperbox.set(form_data['ignore_tupperbox'] == 'true')
                    if 'ignore_apps' in form_data:
                        await config.ignore_apps.set(form_data['ignore_apps'] == 'true')
                    if 'include_thumbnails' in form_data:
                        await config.include_thumbnails.set(form_data['include_thumbnails'] == 'true')
                    if 'detect_proxy_deletes' in form_data:
                        await config.detect_proxy_deletes.set(form_data['detect_proxy_deletes'] == 'true')
                    
                    # Update Tupperbox IDs
                    if 'tupperbox_ids' in form_data:
                        tupperbox_ids = [tid.strip() for tid in form_data['tupperbox_ids'].split(',') if tid.strip()]
                        await config.tupperbox_ids.set(tupperbox_ids)
                    
                    # Update message prefix filters
                    if 'message_prefix_filter' in form_data:
                        prefixes = [p.strip() for p in form_data['message_prefix_filter'].split(',') if p.strip()]
                        await config.message_prefix_filter.set(prefixes)
                    
                    # Update webhook name filters
                    if 'webhook_name_filter' in form_data:
                        filters = [f.strip() for f in form_data['webhook_name_filter'].split(',') if f.strip()]
                        await config.webhook_name_filter.set(filters)
                    
                    # Redirect back to settings page with success message
                    return {
                        "status": 0,
                        "web_content": {"redirect": "../settings?saved=1"}
                    }
                    
                except Exception as e:
                    return {
                        "status": 1,
                        "error_title": "Save Error",
                        "error_message": f"Failed to save configuration: {str(e)}"
                    }
            
            return {
                "status": 1,
                "error_title": "Invalid Request",
                "error_message": "Invalid request method."
            }
            
        except Exception as e:
            return {
                "status": 1,
                "error_title": "Settings Save Error",
                "error_message": f"Failed to save YALC settings: {e}"
            }

    @dashboard_page(name="about", description="About YALC", methods=("GET",), is_owner=False)
    async def dashboard_about(self, user, **kwargs) -> typing.Dict[str, typing.Any]:
        """Dashboard about page for YALC."""
        try:
            source = '''
            <div class="container mt-4">
                <div class="row">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header">
                                <h2><i class="fas fa-info-circle"></i> About YALC</h2>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-8">
                                        <h4>What is YALC?</h4>
                                        <p class="lead">YALC (Yet Another Logging Cog) is a comprehensive logging solution for Red-DiscordBot servers, designed to track and log various Discord events with rich formatting and flexible configuration options.</p>
                                        
                                        <h5>Key Features:</h5>
                                        <ul class="list-group list-group-flush mb-4">
                                            <li class="list-group-item">📝 <strong>Comprehensive Event Logging:</strong> Track message edits, deletions, member joins/leaves, role changes, and more</li>
                                            <li class="list-group-item">🎨 <strong>Rich Embed Formatting:</strong> Beautiful, color-coded embeds with detailed information</li>
                                            <li class="list-group-item">⚙️ <strong>Flexible Configuration:</strong> Per-event channel mapping and granular control</li>
                                            <li class="list-group-item">🚫 <strong>Advanced Filtering:</strong> Ignore specific users, roles, channels, or categories</li>
                                            <li class="list-group-item">🤖 <strong>Smart Bot Detection:</strong> Automatically filter out bot messages and proxy services</li>
                                            <li class="list-group-item">🌐 <strong>Dashboard Integration:</strong> Web-based configuration through Red Dashboard</li>
                                        </ul>
                                        
                                        <h5>Supported Events:</h5>
                                        <div class="row">
                                            <div class="col-md-6">
                                                <ul class="list-unstyled">
                                                    <li>🗑️ Message deletions & bulk deletions</li>
                                                    <li>✏️ Message edits</li>
                                                    <li>👋 Member joins & leaves</li>
                                                    <li>🔨 Bans & unbans</li>
                                                    <li>👤 Member updates (roles, nicknames)</li>
                                                    <li>📝 Channel creation & deletion</li>
                                                </ul>
                                            </div>
                                            <div class="col-md-6">
                                                <ul class="list-unstyled">
                                                    <li>🧵 Thread management</li>
                                                    <li>✨ Role creation & updates</li>
                                                    <li>⚙️ Server configuration changes</li>
                                                    <li>📅 Scheduled events</li>
                                                    <li>❌ Command errors</li>
                                                    <li>🎭 And many more...</li>
                                                </ul>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="card">
                                            <div class="card-header">
                                                <h5>Version Information</h5>
                                            </div>
                                            <div class="card-body">
                                                <p><strong>Version:</strong> 3.0.0</p>
                                                <p><strong>Author:</strong> YALC Team</p>
                                                <p><strong>License:</strong> MIT</p>
                                                <p><strong>Red-DiscordBot:</strong> 3.5+</p>
                                            </div>
                                        </div>
                                        
                                        <div class="card mt-3">
                                            <div class="card-header">
                                                <h5>Links</h5>
                                            </div>
                                            <div class="card-body">
                                                <a href="https://github.com/your-repo/YALC" class="btn btn-outline-primary btn-block mb-2" target="_blank">
                                                    <i class="fab fa-github"></i> Source Code
                                                </a>
                                                <a href="https://discord.gg/your-support" class="btn btn-outline-info btn-block mb-2" target="_blank">
                                                    <i class="fab fa-discord"></i> Support Server
                                                </a>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            '''
            
            return {
                "status": 0,
                "web_content": {"source": source},
            }
        except Exception as e:
            return {
                "status": 1,
                "error_title": "About Page Error",
                "error_message": f"Failed to load YALC about page: {e}"
            }

    # Bind the methods to the cog instance
    cog.dashboard_home = dashboard_home.__get__(cog)
    cog.dashboard_settings = dashboard_settings.__get__(cog)
    cog.dashboard_settings_save = dashboard_settings_save.__get__(cog)
    cog.dashboard_about = dashboard_about.__get__(cog)
    
    # CSRF token helper methods
    async def _generate_csrf_token(self, user, guild) -> str:
        """Generate a CSRF token for the given user and guild."""
        import secrets
        import hashlib
        import time
        
        # Create a unique token based on user, guild, timestamp, and secret
        timestamp = str(int(time.time()))
        secret_key = getattr(cog, '_csrf_secret', secrets.token_hex(32))
        if not hasattr(cog, '_csrf_secret'):
            cog._csrf_secret = secret_key
            
        token_data = f"{user.id}:{guild.id if guild else 'none'}:{timestamp}:{secret_key}"
        token_hash = hashlib.sha256(token_data.encode()).hexdigest()
        
        # Store token with timestamp for validation
        if not hasattr(cog, '_csrf_tokens'):
            cog._csrf_tokens = {}
        cog._csrf_tokens[token_hash] = timestamp
        
        return token_hash

    async def _validate_csrf_token(self, user, guild, request) -> bool:
        """Validate CSRF token from request."""
        if not request or not request.get('form'):
            return False
            
        submitted_token = request.get('form', {}).get('csrf_token')
        if not submitted_token:
            return False
            
        # Check if token exists in our stored tokens
        if not hasattr(cog, '_csrf_tokens') or submitted_token not in cog._csrf_tokens:
            return False
            
        # Validate token age (expire after 1 hour)
        import time
        token_timestamp = int(cog._csrf_tokens[submitted_token])
        current_time = int(time.time())
        
        if current_time - token_timestamp > 3600:  # 1 hour
            # Remove expired token
            del cog._csrf_tokens[submitted_token]
            return False
            
        # Remove token after use (one-time use)
        del cog._csrf_tokens[submitted_token]
        return True

    # Bind CSRF helper methods to cog
    cog._generate_csrf_token = _generate_csrf_token.__get__(cog)
    cog._validate_csrf_token = _validate_csrf_token.__get__(cog)
    
    # Add to pages list for dashboard registration
    if not hasattr(cog, 'pages'):
        cog.pages = []
    
    cog.pages.extend([
        dashboard_home,
        dashboard_settings,
        dashboard_settings_save,
        dashboard_about
    ])

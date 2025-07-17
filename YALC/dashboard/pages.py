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

    @dashboard_page(name="settings", description="Configure YALC logging settings", methods=("GET", "POST"), is_owner=False)
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
            
            # Handle POST requests (form submissions)
            if request and request.get('method') == 'POST':
                # Process form data here
                # This would update the configuration based on form input
                pass
            
            # Count enabled events
            enabled_events = sum(1 for enabled in settings["events"].values() if enabled)
            total_events = len(settings["events"])
            
            # Get configured channels
            configured_channels = sum(1 for channel_id in settings["event_channels"].values() if channel_id)
            
            # Get ignore counts
            ignored_users = len(settings.get("ignored_users", []))
            ignored_roles = len(settings.get("ignored_roles", []))
            ignored_channels = len(settings.get("ignored_channels", []))
            
            source = f'''
            <div class="container mt-4">
                <div class="row">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header">
                                <h3><i class="fas fa-cog"></i> YALC Configuration for {guild.name}</h3>
                            </div>
                            <div class="card-body">
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
                                                <h5>Ignore Settings</h5>
                                            </div>
                                            <div class="card-body">
                                                <p><strong>Ignored Users:</strong> {ignored_users}</p>
                                                <p><strong>Ignored Roles:</strong> {ignored_roles}</p>
                                                <p><strong>Ignored Channels:</strong> {ignored_channels}</p>
                                                <p><strong>Ignore Bots:</strong> {"Yes" if settings.get("ignore_bots", False) else "No"}</p>
                                                <p><strong>Ignore Webhooks:</strong> {"Yes" if settings.get("ignore_webhooks", False) else "No"}</p>
                                                <p><strong>Ignore Tupperbox:</strong> {"Yes" if settings.get("ignore_tupperbox", True) else "No"}</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="row mt-4">
                                    <div class="col-md-12">
                                        <div class="alert alert-info">
                                            <h5><i class="fas fa-info-circle"></i> Configuration Notice</h5>
                                            <p>For detailed configuration, use the bot commands in Discord:</p>
                                            <ul>
                                                <li><code>!yalc enable &lt;event_type&gt;</code> - Enable event logging</li>
                                                <li><code>!yalc setchannel &lt;event_type&gt; &lt;channel&gt;</code> - Set logging channel</li>
                                                <li><code>!yalc settings</code> - View current configuration</li>
                                                <li><code>!yalc ignore user/channel/role &lt;target&gt;</code> - Add ignore rules</li>
                                            </ul>
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
                "error_title": "Settings Error",
                "error_message": f"Failed to load YALC settings: {e}"
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
    cog.dashboard_about = dashboard_about.__get__(cog)
    
    # Add to pages list for dashboard registration
    if not hasattr(cog, 'pages'):
        cog.pages = []
    
    cog.pages.extend([
        dashboard_home,
        dashboard_settings,
        dashboard_about
    ])

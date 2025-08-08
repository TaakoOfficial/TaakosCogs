import typing
try:
    from redbot.core.utils.dashboard import dashboard_page
except ImportError:
    def dashboard_page(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# WTForms integration
import wtforms
from wtforms.validators import Optional

def setup_dashboard_pages(cog):
    """Setup dashboard pages for the YALC cog and bind them to the cog instance."""

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
        """Dashboard settings page for YALC with WTForms integration."""
        try:
            if not guild:
                return {
                    "status": 1,
                    "error_title": "Guild Required",
                    "error_message": "This page requires a guild context."
                }
                
            config = cog.config.guild(guild)
            settings = await config.all()
            
            # WTForms form definition following Red Dashboard pattern
            class YALCSettingsForm(kwargs["Form"]):
                def __init__(self):
                    super().__init__(prefix="yalc_")
                    
                ignore_bots = wtforms.BooleanField("Ignore Bot Messages")
                ignore_webhooks = wtforms.BooleanField("Ignore Webhook Messages")
                ignore_tupperbox = wtforms.BooleanField("Ignore Tupperbox Messages")
                ignore_apps = wtforms.BooleanField("Ignore Application Messages")
                include_thumbnails = wtforms.BooleanField("Include User Thumbnails")
                detect_proxy_deletes = wtforms.BooleanField("Detect Proxy Deletes")
                tupperbox_ids = wtforms.StringField("Tupperbox Bot IDs (comma-separated)", validators=[Optional()])
                message_prefix_filter = wtforms.StringField("Message Prefix Filters (comma-separated)", validators=[Optional()])
                webhook_name_filter = wtforms.StringField("Webhook Name Filters (comma-separated)", validators=[Optional()])
                submit = wtforms.SubmitField("Save Configuration")
            
            # Create form instance
            form = YALCSettingsForm()
            
            # Handle form submission using WTForms validation
            if form.validate_on_submit():
                try:
                    # Update general settings using form data
                    await config.ignore_bots.set(form.ignore_bots.data)
                    await config.ignore_webhooks.set(form.ignore_webhooks.data)
                    await config.ignore_tupperbox.set(form.ignore_tupperbox.data)
                    await config.ignore_apps.set(form.ignore_apps.data)
                    await config.include_thumbnails.set(form.include_thumbnails.data)
                    await config.detect_proxy_deletes.set(form.detect_proxy_deletes.data)
                    
                    # Update string fields with validation
                    if form.tupperbox_ids.data:
                        tupperbox_ids = [tid.strip() for tid in form.tupperbox_ids.data.split(',') if tid.strip()]
                        await config.tupperbox_ids.set(tupperbox_ids)
                    else:
                        await config.tupperbox_ids.set([])
                    
                    if form.message_prefix_filter.data:
                        prefixes = [p.strip() for p in form.message_prefix_filter.data.split(',') if p.strip()]
                        await config.message_prefix_filter.set(prefixes)
                    else:
                        await config.message_prefix_filter.set([])
                    
                    if form.webhook_name_filter.data:
                        filters = [f.strip() for f in form.webhook_name_filter.data.split(',') if f.strip()]
                        await config.webhook_name_filter.set(filters)
                    else:
                        await config.webhook_name_filter.set([])
                    
                    return {
                        "status": 0,
                        "notifications": [{"message": "Configuration updated successfully!", "category": "success"}],
                        "web_content": {"redirect": "./settings"}
                    }
                    
                except Exception as e:
                    return {
                        "status": 1,
                        "notifications": [{"message": f"Failed to save configuration: {str(e)}", "category": "error"}]
                    }
            
            # Pre-populate form with current settings if not a submission
            if not form.is_submitted():
                form.ignore_bots.data = settings.get("ignore_bots", False)
                form.ignore_webhooks.data = settings.get("ignore_webhooks", False)
                form.ignore_tupperbox.data = settings.get("ignore_tupperbox", True)
                form.ignore_apps.data = settings.get("ignore_apps", True)
                form.include_thumbnails.data = settings.get("include_thumbnails", True)
                form.detect_proxy_deletes.data = settings.get("detect_proxy_deletes", True)
                form.tupperbox_ids.data = ",".join(settings.get("tupperbox_ids", []))
                form.message_prefix_filter.data = ",".join(settings.get("message_prefix_filter", []))
                form.webhook_name_filter.data = ",".join(settings.get("webhook_name_filter", []))
            
            # Count enabled events (for display purposes)
            enabled_events = sum(1 for enabled in settings["events"].values() if enabled)
            total_events = len(settings["events"])
            
            # Get configured channels
            configured_channels = sum(1 for channel_id in settings["event_channels"].values() if channel_id)
            
            # Get ignore counts
            ignored_users = len(settings.get("ignored_users", []))
            ignored_roles = len(settings.get("ignored_roles", []))
            ignored_channels = len(settings.get("ignored_channels", []))
            
            return {
                "status": 0,
                "web_content": {
                    "source": f"""
                    <div class="container mt-4">
                        <div class="row">
                            <div class="col-md-12">
                                <div class="card">
                                    <div class="card-header">
                                        <h3><i class="fas fa-cog"></i> YALC Configuration for {guild.name}</h3>
                                    </div>
                                    <div class="card-body">
                                        <div class="row mb-4">
                                            <div class="col-md-4">
                                                <div class="card">
                                                    <div class="card-header">
                                                        <h5>Event Status</h5>
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
                                            <div class="col-md-8">
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
                                                        <div class="alert alert-info mt-3">
                                                            <strong>Note:</strong> Use Discord commands to manage ignore lists:
                                                            <code>/yalc ignore user</code>, <code>/yalc ignore role</code>, <code>/yalc ignore channel</code>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <div class="card">
                                            <div class="card-header">
                                                <h5>YALC Settings</h5>
                                            </div>
                                            <div class="card-body">
                                                {{{{ form|safe }}}}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    """,
                    "form": form
                }
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
        cog.dashboard_home,
        cog.dashboard_settings,
        cog.dashboard_about
    ])

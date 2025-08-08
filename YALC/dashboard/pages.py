# --- Red-Web-Dashboard Third-Party Integration: YALC Settings Page ---
import types
try:
    from redbot.core.utils.dashboard.rpc.thirdparties import DashboardRPC_ThirdParties
    from redbot.core.utils.dashboard import dashboard_page
except ImportError:
    class DashboardRPC_ThirdParties:
        pass
    def dashboard_page(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

@dashboard_page(
    name="yalc_settings",
    description="YALC Settings (API/JSON)",
    methods=("GET", "POST"),
    is_owner=False,
    third_party=True,
    require_guild=True,
)
async def dashboard_yalc_settings(self, user, guild, request: dict = None, **kwargs):
    """
    Red-Web-Dashboard third-party page for YALC settings.
    GET: Returns current settings as JSON.
    POST: Accepts JSON, validates, updates config.
    """
    try:
        config = self.config.guild(guild)
        settings = await config.all()
        safe_keys = [
            "ignore_bots", "ignore_webhooks", "ignore_tupperbox", "ignore_apps",
            "include_thumbnails", "detect_proxy_deletes", "tupperbox_ids",
            "message_prefix_filter", "webhook_name_filter"
        ]
        method = kwargs.get("method", "GET")
        if method == "GET":
            data = {k: settings.get(k) for k in safe_keys}
            return {
                "status": 0,
                "data": data,
                "notifications": [],
            }
        elif method == "POST":
            payload = request or {}
            errors = []
            for k in ["ignore_bots", "ignore_webhooks", "ignore_tupperbox", "ignore_apps", "include_thumbnails", "detect_proxy_deletes"]:
                if k in payload and not isinstance(payload[k], bool):
                    errors.append(f"{k} must be a boolean.")
            for k in ["tupperbox_ids", "message_prefix_filter", "webhook_name_filter"]:
                if k in payload and (not isinstance(payload[k], list) or not all(isinstance(x, str) for x in payload[k])):
                    errors.append(f"{k} must be a list of strings.")
            if errors:
                return {
                    "status": 1,
                    "notifications": [{"message": "Validation error: " + "; ".join(errors), "category": "error"}],
                    "data": {},
                }
            try:
                for k in safe_keys:
                    if k in payload:
                        await getattr(config, k).set(payload[k])
                new_settings = await config.all()
                return {
                    "status": 0,
                    "data": {k: new_settings.get(k) for k in safe_keys},
                    "notifications": [{"message": "Settings updated successfully.", "category": "success"}],
                }
            except Exception as e:
                return {
                    "status": 1,
                    "notifications": [{"message": f"Failed to update settings: {e}", "category": "error"}],
                    "data": {},
                }
        else:
            return {
                "status": 1,
                "notifications": [{"message": "Unsupported method.", "category": "error"}],
                "data": {},
            }
    except Exception as e:
        return {
            "status": 1,
            "notifications": [{"message": f"Internal error: {e}", "category": "error"}],
            "data": {},
        }

# Bind to cog and register page
def _bind_yalc_settings(cog):
    cog.dashboard_yalc_settings = types.MethodType(dashboard_yalc_settings, cog)
    if not hasattr(cog, 'pages'):
        cog.pages = []
    cog.pages.append(cog.dashboard_yalc_settings)
if 'setup_dashboard_pages' in globals():
    old_setup = setup_dashboard_pages
    def new_setup_dashboard_pages(cog):
        old_setup(cog)
        _bind_yalc_settings(cog)
    setup_dashboard_pages = new_setup_dashboard_pages
else:
    # fallback: bind manually if setup_dashboard_pages is not present
    pass

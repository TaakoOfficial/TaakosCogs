import sys
import subprocess
import logging
import pkg_resources

def check_and_install_google_dependencies():
    """
    Ensure google-auth and google-api-python-client are installed. Install with pip if missing.
    """
    required = [
        ("google-auth", "google.oauth2.service_account"),
        ("google-api-python-client", "googleapiclient.discovery")
    ]
    for pkg, import_name in required:
        try:
            __import__(import_name)
        except ImportError:
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", pkg
                ])
                __import__(import_name)
            except Exception as e:
                logging.error(f"Failed to install {pkg}: {e}")
                raise ImportError(f"Could not install required dependency: {pkg}")

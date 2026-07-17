import logging
import subprocess
import sys

log = logging.getLogger("red.taakoscogs.fable.dependencies")


def check_and_install_google_dependencies():
    """
    Ensure google-auth and google-api-python-client are installed. Install with pip if missing.
    """
    required = [
        ("google-auth", "google.oauth2.service_account"),
        ("google-api-python-client", "googleapiclient.discovery"),
    ]
    for pkg, import_name in required:
        try:
            __import__(import_name)
        except ImportError:
            try:
                subprocess.check_call(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        pkg,
                    ],
                )
                __import__(import_name)
            except (subprocess.SubprocessError, ImportError) as e:
                log.error("Failed to install %s: %s", pkg, e)
                raise ImportError(
                    f"Could not install required dependency: {pkg}")

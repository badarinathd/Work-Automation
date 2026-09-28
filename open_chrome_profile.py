#!/usr/bin/env python3
"""Open Google Chrome with the existing profile for cam.badari@gmail.com."""

import json
import subprocess
import sys
from pathlib import Path

EMAIL = "cam.badari@gmail.com"
URLS = ["https://mail.google.com/mail/u/0/", "https://www.linkedin.com/feed/"]

local_state = Path.home() / "Library/Application Support/Google/Chrome/Local State"
profiles = json.loads(local_state.read_text())["profile"]["info_cache"]

# Find the profile folder (e.g. "Default", "Profile 1") signed in with EMAIL
profile_dir = next((d for d, info in profiles.items()
                    if info.get("user_name", "").lower() == EMAIL.lower()), None)
if not profile_dir:
    sys.exit(f"No Chrome profile found for {EMAIL}")

print(f"Opening Chrome profile '{profiles[profile_dir].get('name')}' ({profile_dir})")
subprocess.run(["open", "-na", "Google Chrome", "--args",
                f"--profile-directory={profile_dir}", *URLS], check=True)

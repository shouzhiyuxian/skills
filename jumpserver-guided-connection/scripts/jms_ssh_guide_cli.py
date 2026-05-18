#!/usr/bin/env python3
"""
JumpServer Guided Connection CLI.

This tool provides guided connection functionality for SSH, RDP, VNC, and database protocols.
"""
from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
JUMPSERVER_API_ROOT = REPO_ROOT / "jumpserver-api"
LOCAL_ENTRYPOINT = "jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py"


if __name__ == "__main__":
    if not JUMPSERVER_API_ROOT.exists():
        raise SystemExit(
            "Missing jumpserver-api directory: %s. Register this subskill from the full repository checkout."
            % JUMPSERVER_API_ROOT
        )
    sys.path.insert(0, str(JUMPSERVER_API_ROOT))

    # Import the shared SSH guide CLI module
    ssh_guide_module = import_module("jms_ssh_guide_cli")
    raise SystemExit(ssh_guide_module.main())

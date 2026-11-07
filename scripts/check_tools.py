#!/usr/bin/env python3
"""Prepare local workshop tools and check workstation prerequisites."""
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".lab"
BIN = PRIVATE / "bin"
PLUGIN_DIR = PRIVATE / "sessionmanagerplugin"
BIN.mkdir(parents=True, exist_ok=True)
os.environ["PATH"] = str(BIN) + os.pathsep + os.environ.get("PATH", "")


def install_macos_session_manager_plugin():
    """Download AWS's macOS bundle into the ignored, user-local .lab folder."""
    machine = platform.machine().lower()
    package = {"arm64": "mac_arm64", "aarch64": "mac_arm64", "x86_64": "mac"}.get(machine)
    if not package:
        raise RuntimeError(f"Unsupported macOS processor: {machine}")

    url = f"https://s3.amazonaws.com/session-manager-downloads/plugin/latest/{package}/sessionmanager-bundle.zip"
    print("Session Manager plugin is missing. Downloading the official AWS macOS bundle…", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "ecs-eks-workshop-setup"})
    with urllib.request.urlopen(request, timeout=90) as response:
        archive = response.read()

    with tempfile.TemporaryDirectory(prefix="csci-ssm-") as temporary:
        archive_path = pathlib.Path(temporary) / "plugin.zip"
        archive_path.write_bytes(archive)
        extracted = pathlib.Path(temporary) / "bundle"
        extracted.mkdir()
        with zipfile.ZipFile(archive_path) as package_zip:
            for member in package_zip.infolist():
                member_path = pathlib.PurePosixPath(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise RuntimeError("The AWS plugin archive contains an unsafe path.")
            package_zip.extractall(extracted)

        executables = list(extracted.rglob("bin/session-manager-plugin"))
        if not executables:
            raise RuntimeError("The downloaded AWS bundle did not contain session-manager-plugin.")
        source_root = executables[0].parent.parent
        if PLUGIN_DIR.exists():
            shutil.rmtree(PLUGIN_DIR)
        shutil.copytree(source_root, PLUGIN_DIR)
        plugin = PLUGIN_DIR / "bin" / "session-manager-plugin"
        plugin.chmod(plugin.stat().st_mode | 0o111)

    launcher = BIN / "session-manager-plugin"
    if launcher.exists() or launcher.is_symlink():
        launcher.unlink()
    launcher.symlink_to(PLUGIN_DIR / "bin" / "session-manager-plugin")
    print("Session Manager plugin is ready in this workshop folder.", flush=True)


def prepare_session_manager_plugin():
    if shutil.which("session-manager-plugin"):
        return
    if sys.platform == "darwin":
        try:
            install_macos_session_manager_plugin()
        except Exception as error:
            print(f"Could not prepare the plugin automatically: {error}", flush=True)
            print("AWS setup instructions: https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-macos-overview.html", flush=True)
    elif sys.platform.startswith("win"):
        print("Install the AWS Session Manager plugin: https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-windows.html", flush=True)
    elif sys.platform.startswith("linux"):
        print("Install the AWS Session Manager plugin: https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-linux.html", flush=True)


def run_check(name, args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20)
        output = (result.stdout + result.stderr).strip()
        print(("OK" if result.returncode == 0 else "CHECK") + "  " + name + "\n" + output + "\n", flush=True)
        return result.returncode == 0, output
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"MISSING  {name} — {error}\n", flush=True)
        return False, ""


prepare_session_manager_plugin()
checks = [
    ("Python", [sys.executable, "--version"]),
    ("Git", ["git", "--version"]),
    ("AWS CLI", ["aws", "--version"]),
    ("Session Manager plugin", ["session-manager-plugin", "--version"]),
    ("kubectl", ["kubectl", "version", "--client"]),
]
failed = []
for name, command in checks:
    ok, output = run_check(name, command)
    if not ok:
        failed.append(name)
    elif name == "AWS CLI" and not output.startswith("aws-cli/2."):
        print("Use AWS CLI version 2.", flush=True)
        failed.append(name)
    elif name == "kubectl":
        version = re.search(r"Client Version: v(\d+)\.(\d+)", output)
        if not version or int(version[1]) != 1 or abs(int(version[2]) - 35) > 1:
            print("Use a kubectl client compatible with the 1.35 cluster.", flush=True)
            failed.append(name)

if failed:
    raise SystemExit("Fix these tools, then rerun this task: " + ", ".join(failed))
print("Workstation checks passed. No AWS resources were created or changed.")

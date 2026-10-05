#!/usr/bin/env python3
"""
scripts/release.py - OhMyCrypto Release Preparation and Verification Engine

Follows Sections 9, 12, and 14 of PROJECT_EXECUTION_GUIDE.md:
- Packages macOS application, DMG, and matching corresponding GPL-3.0 source archive
- Enforces GPL-3.0-only licensing and dependency notices
- Generates SHA-256 manifest and checksums
- Verifies package integrity and source correspondence

Usage:
  .venv/bin/python scripts/release.py prepare --version 1.0.0 --channel github --output release/candidate
  .venv/bin/python scripts/release.py verify --manifest release/candidate/manifest.json
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def create_source_archive(output_path: Path, version: str) -> str:
    """Create a pristine matching corresponding source tar.gz archive for GPL-3.0."""
    print("  Creating matching corresponding source archive...")
    tar_name = f"OhMyCrypto-{version}-source.tar.gz"
    tar_file = output_path / tar_name

    def filter_tar(tarinfo):
        exclude_dirs = {".git", ".venv", "node_modules", "dist", "target", "__pycache__", ".agent/evidence/soak24"}
        parts = Path(tarinfo.name).parts
        for ex in exclude_dirs:
            if ex in parts:
                return None
        return tarinfo

    with tarfile.open(tar_file, "w:gz") as tar:
        tar.add(REPO_ROOT, arcname=f"OhMyCrypto-{version}", filter=filter_tar)

    return tar_name


def prepare_release(
    version: str,
    channel: str,
    output_dir: Path,
    arch: str = "arm64",
    skip_source: bool = False,
) -> None:
    print(f"=== Preparing Release {version} for {channel} ===")
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts = []

    # 1. Build frontend dist
    print("  Building desktop frontend...")
    res = subprocess.run(["npm", "--prefix", "desktop", "run", "build"], cwd=str(REPO_ROOT))
    if res.returncode != 0:
        sys.exit(f"Frontend build failed with exit code {res.returncode}")

    # 2. Package sidecar binary if needed
    sidecar_bin = REPO_ROOT / "dist" / "ohmycrypto-sidecar" / "ohmycrypto-sidecar"
    if not sidecar_bin.exists():
        print("  Building sidecar via PyInstaller...")
        res = subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--name", "ohmycrypto-sidecar",
            "--onedir", "--clean", "--noconfirm",
            "src/ohmycrypto/interfaces/sidecar.py",
        ], cwd=str(REPO_ROOT))
        if res.returncode != 0:
            sys.exit(f"PyInstaller build failed with exit code {res.returncode}")

    # 3. Create macOS .app bundle directory structure in output
    app_bundle_dir = output_dir / "OhMyCrypto.app"
    contents_dir = app_bundle_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    # Copy Info.plist
    info_plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>OhMyCrypto</string>
    <key>CFBundleExecutable</key>
    <string>OhMyCrypto</string>
    <key>CFBundleIdentifier</key>
    <string>org.ohmycrypto.desktop</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>OhMyCrypto</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>{version}</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
"""
    with open(contents_dir / "Info.plist", "w", encoding="utf-8") as f:
        f.write(info_plist_content)

    # Launcher executable
    launcher_script = f"""#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
export OHMYCRYPTO_APP_ROOT="$(dirname "$DIR")"
exec "$DIR/sidecar/ohmycrypto-sidecar" "$@"
"""
    launcher_path = macos_dir / "OhMyCrypto"
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write(launcher_script)
    os.chmod(launcher_path, 0o755)

    # Copy sidecar into MacOS directory
    sidecar_target_dir = macos_dir / "sidecar"
    if sidecar_target_dir.exists():
        shutil.rmtree(sidecar_target_dir)
    shutil.copytree(sidecar_bin.parent, sidecar_target_dir)

    # Copy frontend assets into Resources
    shutil.copytree(REPO_ROOT / "desktop" / "dist", resources_dir / "dist", dirs_exist_ok=True)

    print("  Created OhMyCrypto.app bundle.")

    # Ad-hoc sign app bundle on macOS
    if shutil.which("codesign"):
        subprocess.run(["xattr", "-cr", str(app_bundle_dir)], check=False)
        cs_res = subprocess.run([
            "codesign", "-s", "-", "--force", "--deep", str(app_bundle_dir)
        ], capture_output=True, text=True)
        if cs_res.returncode == 0:
            print("  Successfully signed OhMyCrypto.app (ad-hoc Developer/local).")
        else:
            print(f"  Warning: codesign exited with {cs_res.returncode}: {cs_res.stderr}")

    # 4. Create DMG if hdiutil is available (macOS)
    # The DMG is architecture-tagged so arm64 and x86_64 builds never collide.
    dmg_name = f"OhMyCrypto-{version}-{arch}.dmg"
    dmg_path = output_dir / dmg_name
    if shutil.which("hdiutil"):
        print(f"  Creating disk image {dmg_name} via hdiutil...")
        if dmg_path.exists():
            dmg_path.unlink()
        hdi_res = subprocess.run([
            "hdiutil", "create",
            "-volname", "OhMyCrypto",
            "-srcfolder", str(app_bundle_dir),
            "-ov", "-format", "UDZO",
            str(dmg_path),
        ], capture_output=True, text=True)
        if hdi_res.returncode == 0:
            print(f"  Disk image created: {dmg_name}")
            artifacts.append({
                "name": dmg_name,
                "type": "installer_dmg",
                "sha256": compute_sha256(dmg_path),
                "size_bytes": dmg_path.stat().st_size,
            })
        else:
            print(f"  Warning: hdiutil exited with {hdi_res.returncode}: {hdi_res.stderr}")

    # 5. Create matching corresponding source archive (GPL-3.0 requirement).
    # The archive is identical for every architecture, so a multi-arch release
    # publishes it once; --skip-source omits it for per-arch stubs.
    if not skip_source:
        source_tar_name = create_source_archive(output_dir, version)
        source_tar_path = output_dir / source_tar_name
        artifacts.append({
            "name": source_tar_name,
            "type": "corresponding_source_archive",
            "sha256": compute_sha256(source_tar_path),
            "size_bytes": source_tar_path.stat().st_size,
        })

    # 6. Copy LICENSE and NOTICES
    for doc in ["LICENSE", "NOTICES.md", "README.md"]:
        src_doc = REPO_ROOT / doc
        if src_doc.exists():
            shutil.copy2(src_doc, output_dir / doc)
            doc_path = output_dir / doc
            artifacts.append({
                "name": doc,
                "type": "legal_notice",
                "sha256": compute_sha256(doc_path),
                "size_bytes": doc_path.stat().st_size,
            })

    # 7. Write checksums.txt
    checksums_txt = output_dir / "checksums.txt"
    with open(checksums_txt, "w", encoding="utf-8") as f:
        for a in artifacts:
            f.write(f"{a['sha256']}  {a['name']}\n")

    # 8. Write manifest.json
    manifest = {
        "release_id": f"release_{version}_{int(datetime.now(timezone.utc).timestamp())}",
        "version": version,
        "channel": channel,
        "license": "GPL-3.0-only",
        "ui_dials": {
            "DESIGN_VARIANCE": 3,
            "MOTION_INTENSITY": 2,
            "VISUAL_DENSITY": 8,
        },
        "target_os": "macOS 13+",
        "architecture": arch,
        "architectures": ["arm64", "x86_64"],
        "commit": get_git_commit(),
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
    }

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nRelease candidate prepared at: {output_dir}")
    print(f"Manifest written: {manifest_path}")
    print(f"Checksums written: {checksums_txt}")


def verify_release(manifest_path: Path) -> None:
    print(f"=== Verifying Release Manifest: {manifest_path} ===")
    if not manifest_path.exists():
        sys.exit(f"Manifest not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    base_dir = manifest_path.parent
    failures = []

    print(f"Release ID: {manifest.get('release_id')}")
    print(f"Version: {manifest.get('version')}")
    print(f"License: {manifest.get('license')}")
    print(f"Commit: {manifest.get('commit')}")

    for a in manifest.get("artifacts", []):
        file_path = base_dir / a["name"]
        if not file_path.exists():
            failures.append(f"Missing artifact: {a['name']}")
            print(f"  [MISSING] {a['name']}")
            continue

        actual_hash = compute_sha256(file_path)
        expected_hash = a["sha256"]
        if actual_hash != expected_hash:
            failures.append(f"Hash mismatch for {a['name']}: expected {expected_hash}, got {actual_hash}")
            print(f"  [FAIL] {a['name']} (hash mismatch)")
        else:
            print(f"  [OK] {a['name']} (SHA-256: {actual_hash[:16]}...)")

    if failures:
        print(f"\nVerification FAILED with {len(failures)} errors:")
        for err in failures:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nAll release artifacts verified cleanly!")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="OhMyCrypto Release Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prep_parser = subparsers.add_parser("prepare", help="Prepare release candidate")
    prep_parser.add_argument("--version", type=str, default="1.0.0", help="Release version")
    prep_parser.add_argument("--channel", type=str, default="github", help="Distribution channel")
    prep_parser.add_argument("--output", type=str, required=True, help="Output directory")
    prep_parser.add_argument(
        "--arch",
        type=str,
        default="arm64",
        choices=["arm64", "x86_64"],
        help="Target architecture for the DMG (default arm64)",
    )
    prep_parser.add_argument(
        "--skip-source",
        action="store_true",
        help="Omit the GPL-3.0 source archive (published once per release, not per arch)",
    )

    verify_parser = subparsers.add_parser("verify", help="Verify release manifest")
    verify_parser.add_argument("--manifest", type=str, required=True, help="Path to manifest.json")

    args = parser.parse_args()

    if args.command == "prepare":
        prepare_release(
            args.version,
            args.channel,
            Path(args.output),
            arch=args.arch,
            skip_source=args.skip_source,
        )
    elif args.command == "verify":
        verify_release(Path(args.manifest))


if __name__ == "__main__":
    main()

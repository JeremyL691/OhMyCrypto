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
import tempfile
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


def gate_env() -> dict[str, str]:
    """Environment for release subprocesses.

    Inherited PYTHONPATH entries can shadow the project environment with wheels
    built for a different interpreter, which silently breaks builds.
    """
    return {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}


def is_macho(path: Path) -> bool:
    """Return True when the file is a Mach-O executable or library."""
    try:
        res = subprocess.run(
            ["file", "-b", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return False
    return "Mach-O" in res.stdout


def detect_macho_arch(binary: Path) -> str | None:
    """Return the Mach-O architecture of a binary, or None if not determinable.

    A universal binary reports multiple architectures; this returns the set of
    architectures present so a mismatch can be caught before packaging.
    """
    try:
        res = subprocess.run(
            ["file", "-b", str(binary)],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None
    out = res.stdout
    if "arm64" in out and "x86_64" in out:
        return "universal"
    if "arm64" in out:
        return "arm64"
    if "x86_64" in out:
        return "x86_64"
    return None


def pyinstaller_command(arch: str, sidecar_name: str) -> list[str]:
    """Build a PyInstaller invocation whose output matches the requested arch.

    PyInstaller produces binaries for the interpreter that runs it. On an arm64
    host, an x86_64 artifact therefore needs an x86_64 interpreter, selected
    either directly or through Rosetta 2. Onefile mode is used for both
    architectures: macOS 27's codesign classifies a onedir bundle's nested
    stdlib directory (python3.12/), Python.framework and base_library.zip as
    nested code that cannot be signed or validated, while a onefile sidecar is
    a single signable Mach-O object.
    """
    host_arch = platform.machine()
    if arch == host_arch:
        return [
            sys.executable, "-m", "PyInstaller",
            "--name", sidecar_name,
            "--onefile", "--clean", "--noconfirm",
            "src/ohmycrypto/interfaces/sidecar.py",
        ]

    # Cross-architecture: prefer a dedicated venv for that architecture.
    venv_python = REPO_ROOT / f".venv-{arch}" / "bin" / "python"
    if venv_python.exists():
        return [
            "arch", f"-{arch}", str(venv_python), "-m", "PyInstaller",
            "--name", sidecar_name,
            "--onefile", "--clean", "--noconfirm",
            "src/ohmycrypto/interfaces/sidecar.py",
        ]

    # Fall back to Rosetta on an arm64 host.
    if host_arch == "arm64" and arch == "x86_64":
        return [
            "arch", "-x86_64", sys.executable, "-m", "PyInstaller",
            "--name", sidecar_name,
            "--onefile", "--clean", "--noconfirm",
            "src/ohmycrypto/interfaces/sidecar.py",
        ]

    sys.exit(
        f"Cannot build an {arch} sidecar on a {host_arch} host. Provide "
        f".venv-{arch}/bin/python or run on a native {arch} host."
    )


def run_codesign(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["codesign", *args], capture_output=True, text=True)


def sign_and_verify_bundle(app_bundle_dir: Path) -> None:
    """Ad-hoc sign the app bundle and verify it on the current OS.

    The bundle is expected to live outside iCloud File Provider scope (a
    staging directory): File Provider re-adds `com.apple.fileprovider.fpfs#P`
    xattrs to synced paths and codesign refuses to sign a bundle carrying
    "detritus". Every Mach-O object and zip archive inside the bundle is
    signed individually - macOS 27 classifies PyInstaller archives such as
    base_library.zip as nested code even when previous macOS releases sealed
    them as resources - then the outer bundle is signed without --deep and
    finally validated with `codesign --verify --strict`. A bundle that does
    not verify on this OS must fail the release, not ship.
    """
    if not shutil.which("codesign"):
        sys.exit("codesign is not available; cannot sign the app bundle")

    subprocess.run(["xattr", "-cr", str(app_bundle_dir)], capture_output=True, check=False)
    for stray in app_bundle_dir.rglob("._*"):
        try:
            stray.unlink()
        except OSError:
            pass
    for stray in app_bundle_dir.rglob("__MACOSX"):
        if stray.is_dir():
            shutil.rmtree(stray, ignore_errors=True)

    for candidate in sorted(app_bundle_dir.rglob("*")):
        if not candidate.is_file():
            continue
        if is_macho(candidate) or candidate.suffix == ".zip":
            res = run_codesign(["-s", "-", "--force", str(candidate)])
            if res.returncode != 0:
                sys.exit(
                    f"codesign failed for nested object {candidate}: "
                    f"{res.stderr.strip()}"
                )

    res = run_codesign(["-s", "-", "--force", str(app_bundle_dir)])
    if res.returncode != 0:
        sys.exit(f"codesign failed for the app bundle: {res.stderr.strip()}")

    ver = run_codesign(["--verify", "--strict", str(app_bundle_dir)])
    if ver.returncode != 0:
        sys.exit(
            f"Signed bundle does not verify on this OS: {ver.stderr.strip()}"
        )
    print("  Signed and verified OhMyCrypto.app (ad-hoc, codesign --verify --strict).")


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

    # 2. Package sidecar binary for the REQUESTED ARCHITECTURE.
    # Guide section 14: "Rust target selection alone cannot convert Python
    # architecture." A cross-arch DMG must bundle a cross-arch sidecar, so the
    # binary is built with an architecture-matched interpreter (via `arch`)
    # and its Mach-O architecture is verified before packaging.
    sidecar_name = "ohmycrypto-sidecar" if arch == "arm64" else f"ohmycrypto-sidecar-{arch}"
    sidecar_path = REPO_ROOT / "dist" / sidecar_name
    # Onefile builds produce a single executable; onedir builds (legacy) a dir.
    if sidecar_path.is_file():
        sidecar_bin = sidecar_path
    else:
        sidecar_bin = sidecar_path / sidecar_name

    if not sidecar_bin.exists():
        print(f"  Building {arch} sidecar via PyInstaller...")
        res = subprocess.run(
            pyinstaller_command(arch, sidecar_name),
            cwd=str(REPO_ROOT),
            env=gate_env(),
        )
        if res.returncode != 0:
            sys.exit(f"PyInstaller build failed with exit code {res.returncode}")

    detected_arch = detect_macho_arch(sidecar_bin)
    print(f"  Sidecar architecture: {detected_arch} (requested {arch})")
    if detected_arch is not None and detected_arch not in (arch, "universal"):
        sys.exit(
            f"Sidecar architecture mismatch: bundle requests {arch} but sidecar is "
            f"{detected_arch}. Build it with an architecture-matched interpreter."
        )

    # 2.5 Build the Tauri shell binary for the requested architecture.
    # The shell is the bundle's CFBundleExecutable: a real native process that
    # owns the sidecar child and serves the embedded frontend (guide Section
    # 4). A launcher-script executable cannot display the UI and dies at
    # launch, so it is not an acceptable substitute.
    print(f"  Building Tauri shell binary ({arch})...")
    cargo_cmd = ["cargo", "build", "--release"]
    if arch != "arm64":
        cargo_cmd.append(f"--target={arch}-apple-darwin")
    cargo_env = gate_env()
    if arch != "arm64":
        # Cross-compiling needs the rustup toolchain (whose rustc carries the
        # x86_64 std); a PATH cargo from Homebrew only ships the host std and
        # its rustc would silently fail with E0463.
        try:
            toolchain_cargo = subprocess.run(
                ["rustup", "which", "cargo"], capture_output=True, text=True, check=True
            ).stdout.strip()
        except Exception:
            sys.exit(
                "Cross-arch shell build requires rustup with the target's std "
                "(rustup target add x86_64-apple-darwin)."
            )
        if not toolchain_cargo:
            sys.exit("rustup has no default toolchain; run `rustup default stable`.")
        cargo_env["RUSTC"] = str(Path(toolchain_cargo).parent / "rustc")
    cargo_res = subprocess.run(
        cargo_cmd,
        cwd=str(REPO_ROOT / "desktop" / "src-tauri"),
        env=cargo_env,
    )
    if cargo_res.returncode != 0:
        sys.exit(f"Tauri shell build failed with exit code {cargo_res.returncode}")
    shell_bin = (
        REPO_ROOT / "desktop" / "src-tauri" / "target"
        / (f"{arch}-apple-darwin/release" if arch != "arm64" else "release")
        / "ohmycrypto"
    )
    if not shell_bin.exists():
        sys.exit(f"Tauri shell binary missing after build: {shell_bin}")
    shell_arch = detect_macho_arch(shell_bin)
    print(f"  Shell architecture: {shell_arch} (requested {arch})")
    if shell_arch is not None and shell_arch != arch and shell_arch != "universal":
        sys.exit(
            f"Shell architecture mismatch: bundle requests {arch} but shell binary is {shell_arch}."
        )

    # 3. Create the .app bundle in a File-Provider-free staging directory.
    # release/candidate lives under iCloud-synced Desktop storage; codesign
    # refuses to sign bundles carrying File Provider xattrs, which are
    # re-added continuously on synced paths. The bundle is built, signed and
    # verified in staging, then moved into the output directory.
    staging_root = Path(tempfile.mkdtemp(prefix="ohmycrypto-release-"))
    app_bundle_dir = staging_root / "OhMyCrypto.app"
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

    # Executable: the Tauri shell binary (CFBundleExecutable = OhMyCrypto).
    # It owns the sidecar child process and serves the embedded frontend.
    shell_target = macos_dir / "OhMyCrypto"
    shutil.copy2(shell_bin, shell_target)
    os.chmod(shell_target, 0o755)

    # Copy sidecar into MacOS/sidecar (single file for onefile builds).
    sidecar_target_dir = macos_dir / "sidecar"
    sidecar_target_dir.mkdir(parents=True, exist_ok=True)
    if sidecar_bin.is_file():
        shutil.copy2(sidecar_bin, sidecar_target_dir / sidecar_name)
        os.chmod(sidecar_target_dir / sidecar_name, 0o755)
    else:
        shutil.copytree(sidecar_bin.parent, sidecar_target_dir, dirs_exist_ok=True)

    # Copy frontend assets into Resources
    shutil.copytree(REPO_ROOT / "desktop" / "dist", resources_dir / "dist", dirs_exist_ok=True)

    sign_and_verify_bundle(app_bundle_dir)

    # 4. Create the DMG from the pristine staging bundle. Creating it from a
    # bundle already moved into the synced output directory would bake File
    # Provider xattrs into the image and break codesign --verify --strict (and
    # thus Gatekeeper) for clean users.
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
            sys.exit(f"hdiutil exited with {hdi_res.returncode}: {hdi_res.stderr}")

    # Move the signed bundle into the release output directory.
    final_bundle = output_dir / "OhMyCrypto.app"
    if final_bundle.exists():
        shutil.rmtree(final_bundle)
    shutil.move(str(app_bundle_dir), str(final_bundle))
    shutil.rmtree(staging_root, ignore_errors=True)
    print("  Created OhMyCrypto.app bundle.")

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


def aggregate_release(output_dir: Path, version: str, channel: str) -> None:
    """Combine per-architecture prepare runs into one release manifest.

    R13 requires installable arm64 and x86_64 artifacts; a per-arch prepare
    run only registers its own DMG, so the final candidate manifest is
    aggregated here: both architecture DMGs, the GPL corresponding-source
    archive and the legal/document files, each hashed at its current bytes.
    Missing required artifacts fail the aggregation.
    """
    print(f"=== Aggregating Release Manifest for {version} ===")
    required = [
        f"OhMyCrypto-{version}-arm64.dmg",
        f"OhMyCrypto-{version}-x86_64.dmg",
        f"OhMyCrypto-{version}-source.tar.gz",
    ]
    optional_docs = ["LICENSE", "NOTICES.md", "README.md"]

    artifacts = []
    for name in required:
        path = output_dir / name
        if not path.exists():
            sys.exit(f"Aggregation failed: required artifact missing: {name}")
        artifacts.append({
            "name": name,
            "type": (
                "installer_dmg" if name.endswith(".dmg")
                else "corresponding_source_archive"
            ),
            "sha256": compute_sha256(path),
            "size_bytes": path.stat().st_size,
        })
    for name in optional_docs:
        path = output_dir / name
        if not path.exists():
            sys.exit(f"Aggregation failed: required document missing: {name}")
        artifacts.append({
            "name": name,
            "type": "legal_notice",
            "sha256": compute_sha256(path),
            "size_bytes": path.stat().st_size,
        })

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
        "architecture": "arm64+x86_64",
        "architectures": ["arm64", "x86_64"],
        "commit": get_git_commit(),
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
    }

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    checksums_path = output_dir / "checksums.txt"
    with open(checksums_path, "w", encoding="utf-8") as f:
        for a in artifacts:
            f.write(f"{a['sha256']}  {a['name']}\n")

    print(f"  Registered {len(artifacts)} artifacts (both architectures).")
    print(f"Manifest written: {manifest_path}")
    print(f"Checksums written: {checksums_path}")


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

    agg_parser = subparsers.add_parser(
        "aggregate",
        help="Combine per-arch prepare runs into one final manifest",
    )
    agg_parser.add_argument("--version", type=str, default="1.0.0", help="Release version")
    agg_parser.add_argument("--channel", type=str, default="github", help="Distribution channel")
    agg_parser.add_argument("--output", type=str, required=True, help="Output directory")

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
    elif args.command == "aggregate":
        aggregate_release(Path(args.output), args.version, args.channel)


if __name__ == "__main__":
    main()

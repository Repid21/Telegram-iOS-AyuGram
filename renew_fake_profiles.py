#!/usr/bin/env python3
"""Renew Telegram's upstream *fake* CI provisioning profiles after their expiry.

Only intended for non-App-Store, fake-signed GitHub Actions build artifacts.
Rewrites the CMS-encoded test profiles with valid dates. No real Apple signing,
paid developer accounts, server secrets or provisioning IDs are involved.
"""
from __future__ import annotations

import datetime as dt
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def cmd(*args: str) -> bytes:
    return subprocess.check_output(args, stderr=subprocess.PIPE)


def write_profile(path: Path, payload: bytes, cert: Path, key: Path, openssl: str) -> None:
    with tempfile.TemporaryDirectory(prefix="ayu-profiles-") as name:
        source = Path(name) / "input.plist"
        destination = Path(name) / "signed.mobileprovision"
        source.write_bytes(payload)
        cmd(openssl, "cms", "-sign", "-binary", "-nodetach",
            "-in", str(source), "-signer", str(cert), "-inkey", str(key),
            "-outform", "DER", "-out", str(destination))
        decoded = cmd("security", "cms", "-D", "-i", str(destination))
        parsed = plistlib.loads(decoded)
        if parsed["ExpirationDate"] <= dt.datetime.now(dt.timezone.utc).replace(tzinfo=None):
            raise RuntimeError(f"Reissued fake profile is expired: {path}")
        shutil.copyfile(destination, path)


def get_p12(openssl: str, p12: Path, mode: str, out: Path) -> None:
    arguments = [openssl, "pkcs12", "-in", str(p12), "-passin", "pass:",
                 "-out", str(out), "-legacy"] + mode.split()
    try:
        cmd(*arguments)
    except (subprocess.CalledProcessError, OSError):
        cmd(*[x for x in arguments if x != "-legacy"])


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    directory = root / "profiles"
    original_p12 = root / "certs" / "SelfSigned.p12"
    if not original_p12.is_file():
        raise RuntimeError(f"No fake signing identity: {original_p12}")
    profiles = sorted(directory.glob("*.mobileprovision"))
    if not profiles:
        raise RuntimeError(f"No fake profiles: {directory}")

    openssl = ("/opt/homebrew/opt/openssl@3/bin/openssl"
               if Path("/opt/homebrew/opt/openssl@3/bin/openssl").exists()
               else shutil.which("openssl"))
    if not openssl:
        raise RuntimeError("OpenSSL unavailable")

    with tempfile.TemporaryDirectory(prefix="ayu-fake-sign-") as tmp:
        t = Path(tmp)
        cert, key = t / "cert.pem", t / "key.pem"
        get_p12(openssl, original_p12, "-clcerts -nokeys", cert)
        get_p12(openssl, original_p12, "-nocerts -nodes", key)
        try:
            cmd(openssl, "x509", "-in", str(cert), "-checkend", "86400", "-noout")
        except subprocess.CalledProcessError:
            print("Fake test certificate expired; regenerating a new local CI identity.")
            cmd(openssl, "req", "-x509", "-newkey", "rsa:2048", "-sha256",
                "-days", "3650", "-nodes",
                "-subj", "/C=US/O=AyuGram/OU=C67CF9S4VU/CN=AyuGram CI Fake Signing",
                "-keyout", str(key), "-out", str(cert))
            cmd(openssl, "pkcs12", "-export", "-inkey", str(key),
                "-in", str(cert), "-out", str(original_p12), "-passout", "pass:")
            print("Replaced expired fake CI signing identity.")

        certificate_der = cmd(openssl, "x509", "-in", str(cert), "-outform", "DER")
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        refreshed_until = now + dt.timedelta(days=3650)
        for path in profiles:
            raw = cmd("security", "cms", "-D", "-i", str(path))
            obj = plistlib.loads(raw)
            obj["CreationDate"] = now
            obj["ExpirationDate"] = refreshed_until
            obj["DeveloperCertificates"] = [certificate_der]
            if "DER-Encoded-Profile" in obj:
                del obj["DER-Encoded-Profile"]
            payload = plistlib.dumps(obj, fmt=plistlib.FMT_XML)
            write_profile(path, payload, cert, key, openssl)
            print(f"Renewed fake profile: {path.name}, expires {refreshed_until.date()}")

    print(f"Refreshed {len(profiles)} fake CI profiles.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import re
import ssl
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from publicsuffix2 import get_sld, get_tld


INPUT_FILE = Path("subdomains.txt")
TIMEOUT = 5
READ_LIMIT = 8192
USER_AGENT = "Mozilla/5.0 SubdomainAvailabilityChecker/1.0"
LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
SSL_CONTEXT = ssl._create_unverified_context()


def normalize_hostname(line):
    value = line.strip()
    if not value:
        return None

    parsed = urlsplit(value if "://" in value else "//" + value)
    try:
        hostname = parsed.hostname
        parsed.port  # Reject malformed ports.
    except ValueError:
        return None

    if not hostname:
        return None
    hostname = hostname.rstrip(".").lower()
    labels = hostname.split(".")
    if len(hostname) > 253 or len(labels) < 2:
        return None
    if not all(LABEL_RE.fullmatch(label) for label in labels):
        return None
    return hostname


def load_hostnames():
    if not INPUT_FILE.exists():
        print("Error: subdomains.txt not found.")
        return None

    text = INPUT_FILE.read_text(encoding="utf-8")
    if not text.strip():
        print("Error: subdomains.txt is empty.")
        return None

    hostnames = []
    seen = set()
    for line in text.splitlines():
        hostname = normalize_hostname(line)
        if hostname and hostname not in seen:
            seen.add(hostname)
            hostnames.append(hostname)

    if not hostnames:
        print("Error: no valid hostnames found.")
        return None
    return hostnames


def get_base_domain(hostnames):
    domains = set()
    for hostname in hostnames:
        suffix = get_tld(hostname, strict=True)
        domain = get_sld(hostname, strict=True)
        if not suffix or not domain or domain == suffix:
            return None
        domains.add(domain)

    if len(domains) != 1:
        return None
    return domains.pop()


def has_content(url):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT, context=SSL_CONTEXT) as response:
            return bool(response.read(READ_LIMIT))
    except HTTPError as error:
        try:
            return bool(error.read(READ_LIMIT))
        except (OSError, ValueError):
            return False
        finally:
            error.close()
    except (URLError, HTTPException, OSError, ValueError):
        return False


def main():
    try:
        hostnames = load_hostnames()
    except (OSError, UnicodeError) as error:
        print(f"Error: could not read subdomains.txt: {error}")
        return
    if hostnames is None:
        return

    base_domain = get_base_domain(hostnames)
    if base_domain is None:
        print("Error: base domain cannot be determined unambiguously.")
        return

    output_path = Path(f"{base_domain}.csv")
    total = len(hostnames)
    checked = 0
    available = 0

    print(f"Loaded: {total} subdomains")
    print(f"Base domain: {base_domain}")
    print(f"Output: {output_path}\n")

    try:
        with output_path.open("w", encoding="utf-8", newline="") as output:
            for number, hostname in enumerate(hostnames, 1):
                working_url = None
                result = "FAIL"
                for protocol in ("https", "http"):
                    url = f"{protocol}://{hostname}"
                    if has_content(url):
                        working_url = url
                        result = f"{protocol.upper()} OK"
                        break

                checked += 1
                if working_url:
                    available += 1
                    output.write(f"{working_url}, {base_domain}\n")
                    output.flush()
                print(f"[{number}/{total}] {hostname} .......... {result}", flush=True)
    except KeyboardInterrupt:
        print("\nInterrupted by user.\n")
        print(f"Checked:   {checked}")
        print(f"Available: {available}")
        print(f"Saved to:  {output_path}")
        return
    except OSError as error:
        print(f"Error: could not write {output_path}: {error}")
        return

    print("\nFinished.")
    print(f"Checked:   {checked}")
    print(f"Available: {available}")
    print(f"Failed:    {checked - available}")
    print(f"Saved to:  {output_path}")


if __name__ == "__main__":
    main()

"""Render a candidate Caddy config without replacing unrelated sites or logging."""
import argparse
from pathlib import Path
import re


UPSTREAMS = {
    "ai-radar-api": "172.18.0.2",
    "ai-radar-web": "172.18.0.4",
    "ai-radar-aisi": "172.18.0.5",
    "ai-radar-openprice": "172.18.0.6",
    "ai-radar-pricein": "172.18.0.7",
    "ai-radar-aiprice": "172.18.0.8",
}
FEED_PATHS = " /data/latest.json /data/alerts-latest.json /data/v1/snapshots/* /data/v1/catalogs/*"


def render(source):
    result = source
    for alias, address in UPSTREAMS.items():
        result = re.sub(r"(?<=reverse_proxy )" + re.escape(alias) + r"(?=:)", address, result)
        result = re.sub(r"(?<=import brand_site )" + re.escape(alias) + r"\b", address, result)
    lines = []
    for line in result.splitlines():
        matcher, marker, comment = line.partition("#")
        if matcher.strip().startswith("@api path /api/*") and " /health" in matcher:
            matcher = matcher.rstrip()
            for path in FEED_PATHS.split():
                if path not in matcher.split():
                    matcher += " " + path
            line = matcher + (" #" + comment if marker else "")
        lines.append(line)
    result = "\n".join(lines) + "\n"
    if "172.18.0.2:8000" not in result or "172.18.0.4:3000" not in result:
        raise ValueError("Expected production API/Web upstreams were not found")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.candidate.resolve():
        parser.error("Write a separate candidate, validate it, then reload Caddy")
    args.candidate.write_text(render(args.source.read_text()), encoding="utf-8")
    print("Candidate written; validate fixed Compose IPs and caddy validate before reload")


if __name__ == "__main__":
    main()

"""Admission check for a background job; compatible with production Python 3.6."""
import argparse
from pathlib import Path


def available_mib(meminfo):
    for line in meminfo.splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    raise ValueError("MemAvailable missing; cannot safely start background work")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--required-mib", required=True, type=int)
    args = parser.parse_args()
    free = available_mib(Path("/proc/meminfo").read_text())
    if free < args.required_mib:
        print("background job deferred: available={} MiB, required={} MiB".format(free, args.required_mib))
        return 75
    print("background memory budget passed: available={} MiB".format(free))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

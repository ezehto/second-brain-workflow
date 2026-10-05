#!/usr/bin/env python3
"""Generate the deterministic scratch corpus for the mount spike (plan section 8).

Creates COUNT Markdown files of 1 to 4 KB with frontmatter, spread over 20
folders up to 3 levels deep, with names containing spaces and non-ASCII
characters. Refuses any root that is not under /mnt/d/sbw-spike/.

Usage: gen_corpus.py [--root "/mnt/d/sbw-spike/Spike Vault"] [--count 5000] [--seed 20261005]
"""
import argparse
import os
import random
import sys

ALLOWED_PREFIX = "/mnt/d/sbw-spike/"
MARKER = ".sbw-spike-scratch"
MARKER_TEXT = "sbw-spike scratch vault: safe to write, safe to delete\n"
DEFAULT_ROOT = "/mnt/d/sbw-spike/Spike Vault"

# 20 folders, 3 levels deep at most. Some names carry spaces or non-ASCII.
FOLDERS = [
    "Projects", "Projects/Alpha", "Projects/Alpha/Notes", "Projects/Béta",
    "Projects/Béta/Meeting notes", "Knowledge", "Knowledge/Networking",
    "Knowledge/Networking/DNS and DHCP", "Knowledge/Databases",
    "Knowledge/日本語", "Decisions", "Decisions/2025", "Decisions/2026",
    "Standups", "Standups/2026 Q3", "Inbox", "Inbox/Über Quick Capture",
    "Archive", "Archive/Old projects", "Archive/Old projects/Ñandú",
]
NAME_WORDS = ["Café", "naïve", "plan", "review", "über", "notes", "日本語", "résumé",
              "design", "söke", "queue", "retro", "Ångström", "backup", "cache", "ünit test"]
BODY_WORDS = ("alpha beta gamma delta epsilon latency throughput mount vault index note task "
              "project decision review standup docker compose python backend frontend "
              "database query cache poll scan hash rename replace atomic windows linux "
              "obsidian markdown frontmatter wikilink backlink tag status owner").split()
TAGS = ["spike", "infra", "backend", "review", "idea", "ops"]


def check_root(root, allow_any=False):
    """Return the resolved root; raise SystemExit unless it is under the scratch prefix."""
    real = os.path.realpath(root)
    if allow_any:
        return real
    if not (real + "/").startswith(ALLOWED_PREFIX) or real + "/" == ALLOWED_PREFIX:
        sys.exit(f"refusing: {root!r} resolves to {real!r}, which is not under {ALLOWED_PREFIX}")
    return real


def make_note(rng, index, title):
    target = rng.randint(1024, 4096)
    fm = (f"---\ntype: knowledge\ntitle: {title}\nstatus: active\n"
          f"tags: [{rng.choice(TAGS)}, {rng.choice(TAGS)}]\n"
          f"created: 2026-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}\nid: {index:05d}\n---\n\n")
    body = [f"# {title}\n"]
    size = len(fm) + len(body[0])
    while size < target:
        line = " ".join(rng.choice(BODY_WORDS) for _ in range(rng.randint(8, 18)))
        if rng.random() < 0.05:
            line += f" [[{rng.choice(NAME_WORDS)} {rng.randint(0, 4999):05d}]]"
        body.append(line + "\n")
        size += len(line.encode("utf-8")) + 1
    return fm + "\n".join(body)


def generate(root, count=5000, seed=20261005, allow_any=False):
    real = check_root(root, allow_any)
    rng = random.Random(seed)
    os.makedirs(real, exist_ok=True)
    with open(os.path.join(real, MARKER), "w", encoding="utf-8") as fh:
        fh.write(MARKER_TEXT)
    for folder in FOLDERS:
        os.makedirs(os.path.join(real, folder), exist_ok=True)
    total_bytes = 0
    for i in range(count):
        folder = FOLDERS[i % len(FOLDERS)]
        title = f"{rng.choice(NAME_WORDS)} {rng.choice(NAME_WORDS)} {i:05d}"
        content = make_note(rng, i, title)
        data = content.encode("utf-8")
        total_bytes += len(data)
        with open(os.path.join(real, folder, title + ".md"), "wb") as fh:
            fh.write(data)
    return {"root": real, "files": count, "folders": len(FOLDERS), "bytes": total_bytes, "seed": seed}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--count", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=20261005)
    a = ap.parse_args()
    import json
    print(json.dumps(generate(a.root, a.count, a.seed)))


if __name__ == "__main__":
    main()

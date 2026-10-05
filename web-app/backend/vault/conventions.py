"""The vault's conventions as data: one place for every component that needs them.

Sources: design section D (folders, templates, frontmatter), plan sections 2.3
(status vocabularies), 2.5 (sanitising sets), 2.10 (date keys) and 2.11
(required keys). The skill's reference/conventions.md restates these for the
Claude Code commands; keep the two in step.
"""

# The six Phase 1 types (design D). Anything else is indexed as written (2.10).
KNOWN_TYPES = ("task", "project", "daily", "decision", "lesson", "capture")

# Type given to a note with no usable `type` (2.10).
DEFAULT_TYPE = "note"

# Where each type lives (design D; checked as F4 in 2.11). Daily notes live in a
# year folder below this one: 01-Daily/YYYY/YYYY-MM-DD.md.
TYPE_FOLDERS = {
    "task": "02-Work/Tasks",
    "project": "02-Work/Projects",
    "daily": "01-Daily",
    "decision": "05-Knowledge/Decisions",
    "lesson": "05-Knowledge/Lessons",
    "capture": "00-Inbox",
}

# Phase 1 folders (design D) that the writer and commands may create when missing (2.5).
PHASE_1_FOLDERS = (
    "00-Inbox",
    "01-Daily",
    "02-Work/Projects",
    "02-Work/Tasks",
    "05-Knowledge/Decisions",
    "05-Knowledge/Lessons",
    "08-System/Templates",
)

TEMPLATES_FOLDER = "08-System/Templates"
TEMPLATE_NAMES = ("task.md", "project.md", "daily.md", "decision.md", "lesson.md", "capture.md")

# Status vocabulary per type (2.3). `daily` has no status key; other types have none enforced.
STATUSES = {
    "task": ("inbox", "planned", "in-progress", "blocked", "review", "done", "cancelled"),
    "project": ("active", "paused", "done", "archived"),
    "decision": ("proposed", "accepted", "superseded", "rejected"),
    "lesson": ("active", "archived"),
    "capture": ("inbox", "triaged", "dismissed"),
}

DEFAULT_STATUS = {
    "task": "planned",
    "project": "active",
    "decision": "proposed",
    "lesson": "active",
    "capture": "inbox",
}

PRIORITIES = ("low", "medium", "high")

# Keys read with the date rule of 2.10.
DATE_KEYS = ("created", "due", "decided")

# Keys that must be present and not null, per known type (2.11, F2).
REQUIRED_KEYS = {
    "task": ("type", "status", "created"),
    "project": ("type", "status", "created"),
    "decision": ("type", "status", "created"),
    "lesson": ("type", "status", "created"),
    "capture": ("type", "status", "created"),
    "daily": ("type", "created"),
}

# Link targets with these extensions on their final path segment are attachments,
# not notes, and are not stored (2.8). Matched case-insensitively.
ATTACHMENT_EXTENSIONS = frozenset(
    [
        "png", "jpg", "jpeg", "gif", "bmp", "svg", "webp", "avif", "pdf",
        "mp3", "wav", "m4a", "ogg", "flac", "3gp",
        "mp4", "webm", "mov", "mkv", "ogv",
        "canvas", "base",
    ]
)  # fmt: skip

# File-name sanitising sets (2.5 rules 2, 3 and 6).
CONTROL_CHARACTERS = frozenset([chr(code) for code in range(0x20)] + ["\x7f"])
WINDOWS_ILLEGAL_CHARACTERS = frozenset('\\/:*?"<>|')
LINK_BREAKING_CHARACTERS = frozenset("#^[]")
RESERVED_DEVICE_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{n}" for n in range(1, 10)]
    + [f"LPT{n}" for n in range(1, 10)]
)

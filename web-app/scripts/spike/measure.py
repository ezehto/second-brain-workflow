#!/usr/bin/env python3
"""Mount spike measurements (plan section 8). Standard library only.

Every subcommand prints one JSON object on stdout. Every subcommand that
touches the filesystem refuses a root that is not the scratch vault: either
under /mnt/d/sbw-spike/ (host side) or containing the marker file that
gen_corpus.py writes (container side, where the mount is /vault).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

ALLOWED_PREFIX = "/mnt/d/sbw-spike/"
MARKER = ".sbw-spike-scratch"

# ---- COMMANDS ----
COMMANDS = {}

# ---- helpers ----
def refuse(msg):
    sys.stderr.write(f"refusing: {msg}\n")
    sys.exit(2)


def guard(root):
    """Return the resolved scratch root, or exit 2. Never returns a path that could be real data."""
    real = os.path.realpath(root)
    under_prefix = (real + "/").startswith(ALLOWED_PREFIX) and real + "/" != ALLOWED_PREFIX
    marker = os.path.join(real, MARKER)
    has_marker = False
    if os.path.isfile(marker):
        with open(marker, encoding="utf-8") as fh:
            has_marker = fh.read().startswith("sbw-spike scratch vault")
    if not (under_prefix or has_marker):
        refuse(f"{root!r} resolves to {real!r}: not under {ALLOWED_PREFIX} and has no {MARKER} marker")
    if not os.path.isdir(real):
        refuse(f"{real!r} is not a directory (run gen_corpus.py first)")
    return real


def inside(root, path):
    """Resolve path (absolute or relative to root) and require it to be under root."""
    p = os.path.realpath(os.path.join(root, path))
    if not (p + "/").startswith(root.rstrip("/") + "/"):
        refuse(f"{path!r} is outside {root!r}")
    return p


def rel(root, path):
    return os.path.relpath(path, root)


def md_files(root):
    """Walk like the indexer will: skip dot-directories and dotfiles, yield *.md paths."""
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for f in fns:
            if f.endswith(".md") and not f.startswith("."):
                yield os.path.join(dp, f)


def stat_walk(root):
    sig = {}
    for p in md_files(root):
        st = os.stat(p)
        sig[p] = (st.st_mtime_ns, st.st_size)
    return sig


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def timing(label, runs_ms, files):
    """ms per file from the median run, projected to 1,000 and 5,000 notes (seconds)."""
    med = median(runs_ms)
    per = med / files if files else 0.0
    return {"median_ms": round(med, 3), "ms_per_file": round(per, 5),
            "projected_1000_s": round(per * 1000 / 1000, 4), "projected_5000_s": round(per * 5000 / 1000, 4)}


def base(name, root):
    return {"measurement": name, "root": root, "uid": os.getuid(), "gid": os.getgid(),
            "python": sys.version.split()[0], "t_start": time.time()}


def exc_info(e):
    return {"type": type(e).__name__, "errno": getattr(e, "errno", None), "strerror": getattr(e, "strerror", None)}


def scratch_dir(root, name):
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    return d


def rm_tree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


# ---- commands: each is (setup(parser), run(args)) ----
def _root_arg(p):
    p.add_argument("--root", default="/vault", help="scratch vault root (default /vault, the container mount)")


def cmd_mounts_setup(p):
    _root_arg(p)


def cmd_mounts(a):
    root = guard(a.root)
    out = base("mounts", root)
    best = None
    with open("/proc/mounts", encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            mp = parts[1].replace("\\040", " ")
            if (root + "/").startswith(mp.rstrip("/") + "/") and (best is None or len(mp) > len(best[1])):
                best = (parts[0], mp, parts[2], parts[3])
    out.update(marker_present=os.path.isfile(os.path.join(root, MARKER)), md_files=sum(1 for _ in md_files(root)),
               top_level=sorted(os.listdir(root))[:8],
               mount=dict(zip(("device", "mount_point", "fstype", "options"), best)) if best else None)
    return out


def cmd_scan_setup(p):
    _root_arg(p)
    p.add_argument("--warm", type=int, default=5, help="warm runs after the first (cold) run")


def cmd_scan(a):
    root = guard(a.root)
    runs, files = [], 0
    for _ in range(1 + a.warm):
        t = time.perf_counter()
        files = len(stat_walk(root))
        runs.append((time.perf_counter() - t) * 1000)
    out = base("scan", root)
    warm = runs[1:]
    out.update(files=files, cold_ms=round(runs[0], 3), warm_ms=[round(x, 3) for x in warm],
               warm_median_ms=round(median(warm), 3),
               note="cold = first run in this process, not a dropped page cache")
    out.update(timing("scan", warm, files))
    return out


def cmd_hash_setup(p):
    _root_arg(p)
    p.add_argument("--runs", type=int, default=3)


def cmd_hash(a):
    import hashlib
    root = guard(a.root)
    runs, files, nbytes = [], 0, 0
    for _ in range(a.runs):
        t = time.perf_counter()
        files = nbytes = 0
        for p in md_files(root):
            with open(p, "rb") as fh:
                data = fh.read()
            hashlib.sha256(data).hexdigest()
            files += 1
            nbytes += len(data)
        runs.append((time.perf_counter() - t) * 1000)
    out = base("hash", root)
    out.update(files=files, bytes=nbytes, runs_ms=[round(x, 3) for x in runs], first_run_ms=round(runs[0], 3))
    out.update(timing("hash", runs, files))
    return out


def cmd_mtime_setup(p):
    _root_arg(p)


def cmd_mtime(a):
    from math import gcd
    from functools import reduce
    root = guard(a.root)
    d = scratch_dir(root, "_mtime")
    f = os.path.join(d, "probe.md")
    with open(f, "w") as fh:
        fh.write("one\n")
    m1 = os.stat(f).st_mtime_ns
    time.sleep(0.05)
    with open(f, "w") as fh:
        fh.write("two\n")
    m2 = os.stat(f).st_mtime_ns
    # granularity: gcd of the mtimes of 40 files written back to back
    stamps = []
    for i in range(40):
        g = os.path.join(d, f"g{i}.md")
        with open(g, "w") as fh:
            fh.write(str(i))
        stamps.append(os.stat(g).st_mtime_ns)
        time.sleep(0.001)
    gran = reduce(gcd, stamps)
    # distinct mtimes when one file is rewritten 40 times at 1 ms spacing
    seen = set()
    for i in range(40):
        with open(f, "w") as fh:
            fh.write(str(i))
        seen.add(os.stat(f).st_mtime_ns)
        time.sleep(0.001)
    rm_tree(d)
    out = base("mtime", root)
    out.update(write1_ns=m1, write2_ns=m2, delta_ns=m2 - m1, granularity_ns=gran,
               distinct_mtimes_in_40_writes_1ms_apart=len(seen),
               resolution_note=f"gcd of 40 mtime_ns values is {gran} ns; 50 ms apart writes differ by {m2 - m1} ns")
    return out


def cmd_replace_setup(p):
    _root_arg(p)
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--target", help="replace this existing file (n=1) instead of the scratch target")
    p.add_argument("--dir", help="scratch folder under the root for the loop (default _replace, removed afterwards); "
                                 "a given folder is left in place and only the loop's own file is removed")
    p.add_argument("--seconds", type=float, help="keep replacing for this long instead of --n times")
    p.add_argument("--pause-ms", type=float, default=0.0, help="sleep between replaces")


def atomic_replace(path, payload):
    """Temp file in the same directory, fsync, os.replace: the writer's pattern."""
    d = os.path.dirname(path)
    tmp = os.path.join(d, f".x.sbw-tmp-{os.getpid()}-{time.monotonic_ns()}")
    with open(tmp, "wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cmd_replace(a):
    root = guard(a.root)
    out = base("replace", root)
    if a.target:
        path = inside(root, a.target)
        with open(path, "rb") as fh:
            orig = fh.read()
        stamp = time.strftime("%H:%M:%S")
        payload = orig + f"\nREPLACED {stamp}\n".encode()
        res = {"ok": 0, "failures": 0, "exception": None, "content_correct": None}
        try:
            atomic_replace(path, payload)
            res["ok"] = 1
        except Exception as e:
            res["failures"] = 1
            res["exception"] = exc_info(e)
        with open(path, "rb") as fh:
            now = fh.read()
        res["content_correct"] = now == payload
        res["content_unchanged"] = now == orig
        out.update(mode="target", n=1, target=rel(root, path), t_replace=time.time(), leftover_tmp=len(
            [f for f in os.listdir(os.path.dirname(path)) if f.startswith(".x.sbw-tmp-")]), per_replace_ms=None, **res)
        return out
    custom = a.dir is not None
    d = inside(root, a.dir) if custom else os.path.join(root, "_replace")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "m6-loop.md" if custom else "target.md")
    with open(path, "w") as fh:
        fh.write("initial\n")
    ok, fails, times = 0, [], []
    deadline = time.monotonic() + a.seconds if a.seconds else None
    i = -1
    while True:
        i += 1
        if deadline is not None:
            if time.monotonic() >= deadline:
                break
        elif i >= a.n:
            break
        if a.pause_ms and i:
            time.sleep(a.pause_ms / 1000)
        payload = (f"---\ntype: knowledge\n---\n\nreplace {i}\n" + "x" * (1024 + i)).encode()
        t = time.perf_counter()
        try:
            atomic_replace(path, payload)
            with open(path, "rb") as fh:
                correct = fh.read() == payload
            if correct:
                ok += 1
            else:
                fails.append({"i": i, "problem": "content mismatch"})
        except Exception as e:
            fails.append({"i": i, **exc_info(e)})
        times.append((time.perf_counter() - t) * 1000)
    leftover = len([f for f in os.listdir(d) if f.startswith(".x.sbw-tmp-")])
    if custom:
        os.unlink(path)
    else:
        rm_tree(d)
    out.update(mode="scratch", n=len(times), dir=rel(root, d), seconds=a.seconds, ok=ok, failures=len(fails), failure_detail=fails[:5], leftover_tmp=leftover,
               per_replace_ms=round(sum(times) / len(times), 3) if times else None, max_replace_ms=round(max(times), 3) if times else None)
    return out


def cmd_create_setup(p):
    _root_arg(p)
    p.add_argument("--name", default="created-in-container.md")


def cmd_create(a):
    root = guard(a.root)
    d = scratch_dir(root, "_m7")
    path = os.path.join(d, a.name)
    umask = os.umask(0)
    os.umask(umask)
    with open(path, "w") as fh:
        fh.write(f"---\ntype: knowledge\n---\n\ncreated by uid {os.getuid()} in the container\n")
        fh.flush()
        os.fsync(fh.fileno())
    st, dst = os.stat(path), os.stat(d)
    out = base("create", root)
    out.update(path=rel(root, path), mode=oct(st.st_mode & 0o7777), size=st.st_size, file_uid=st.st_uid,
               file_gid=st.st_gid, dir_mode=oct(dst.st_mode & 0o7777), dir_uid=dst.st_uid, dir_gid=dst.st_gid,
               umask=oct(umask), mtime_ns=st.st_mtime_ns)
    return out


def cmd_case_setup(p):
    _root_arg(p)


def cmd_case(a):
    root = guard(a.root)
    d = scratch_dir(root, "_m10")
    out = base("case", root)
    first, second = os.path.join(d, "Case.md"), os.path.join(d, "case.md")
    with open(first, "w") as fh:
        fh.write("upper\n")
    out["created_first"] = "Case.md"
    try:
        with open(second, "x") as fh:
            fh.write("lower\n")
        out["created_second"] = "case.md"
    except Exception as e:
        out["created_second"] = exc_info(e)
    listing = sorted(os.listdir(d))
    out.update(listing=listing, distinct_files=len(listing),
               case_sensitive=len(listing) == 2, content_Case_md=open(first).read().strip())
    rm_tree(d)
    return out


def cmd_illegal_setup(p):
    _root_arg(p)
    p.add_argument("--keep", action="store_true", help="leave _m11 in place so the caller can inspect it from Windows")


def cmd_illegal(a):
    root = guard(a.root)
    d = scratch_dir(root, "_m11")
    attempts = []
    for name in ("a:b.md", "a?b.md"):
        try:
            with open(os.path.join(d, name), "x") as fh:
                fh.write("x")
            attempts.append({"name": name, "created": True})
        except Exception as e:
            attempts.append({"name": name, "created": False, **exc_info(e)})
    out = base("illegal", root)
    out.update(attempts=attempts, listing=sorted(os.listdir(d)), kept=a.keep)
    if not a.keep:
        rm_tree(d)
    return out


def cmd_rowrite_setup(p):
    _root_arg(p)


def cmd_rowrite(a):
    import errno
    root = guard(a.root)
    existing = next(md_files(root))
    created = []
    attempts = []

    def attempt(name, fn):
        try:
            fn()
            attempts.append({"op": name, "succeeded": True, "errno": None})
        except OSError as e:
            attempts.append({"op": name, "succeeded": False, "errno": e.errno, "errno_name": errno.errorcode.get(e.errno)})

    def make_file():
        p = os.path.join(root, ".sbw-ro-probe")
        with open(p, "w") as fh:
            fh.write("x")
        created.append(p)

    def open_append():
        with open(existing, "ab"):  # opens for write, writes nothing
            pass

    def make_dir():
        p = os.path.join(root, ".sbw-ro-probe-dir")
        os.mkdir(p)
        created.append(p)

    attempt("create_file", make_file)
    attempt("open_existing_for_append", open_append)
    attempt("mkdir", make_dir)
    for p in created:  # only reached when the mount was NOT read-only
        rm_tree(p) if os.path.isdir(p) else os.unlink(p)
    out = base("rowrite", root)
    out.update(attempts=attempts, all_erofs=all(x["errno"] == errno.EROFS for x in attempts))
    return out


def cmd_poll_setup(p):
    _root_arg(p)
    p.add_argument("--interval", type=float, default=10.0)
    p.add_argument("--duration", type=float, default=600.0)


def cmd_poll(a):
    root = guard(a.root)
    prev, passes, changed_total = None, [], 0
    cpu0, wall0 = time.process_time(), time.monotonic()
    while time.monotonic() - wall0 < a.duration:
        t0 = time.monotonic()
        sig = stat_walk(root)
        if prev is not None:
            changed_total += sum(1 for k, v in sig.items() if prev.get(k) != v) + len(set(prev) - set(sig))
        prev = sig
        passes.append((time.monotonic() - t0) * 1000)
        time.sleep(max(0.0, a.interval - (time.monotonic() - t0)))
    wall, cpu = time.monotonic() - wall0, time.process_time() - cpu0
    files = len(prev or {})
    out = base("poll", root)
    out.update(interval_s=a.interval, duration_s=round(wall, 2), files=files, passes=len(passes),
               mean_pass_ms=round(sum(passes) / len(passes), 3), max_pass_ms=round(max(passes), 3),
               min_pass_ms=round(min(passes), 3), median_pass_ms=round(median(passes), 3),
               first_pass_ms=round(passes[0], 3),
               over_interval=sum(1 for p in passes if p / 1000 > a.interval), changed_seen=changed_total,
               ms_per_file_mean=round(sum(passes) / len(passes) / files, 5) if files else None,
               process_cpu_s=round(cpu, 3), process_cpu_pct_of_core=round(100 * cpu / wall, 2))
    return out


def cmd_watch_setup(p):
    _root_arg(p)
    p.add_argument("--files", nargs="+", required=True, help="paths relative to root (or absolute under it)")
    p.add_argument("--expect", type=int, required=True, help="stop after this many change events")
    p.add_argument("--distinct", action="store_true", help="count distinct files with an event, not events")
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--interval", type=float, default=0.5)


def cmd_watch(a):
    root = guard(a.root)
    paths = [inside(root, f) for f in a.files]
    sig = {p: (os.stat(p).st_mtime_ns, os.stat(p).st_size) for p in paths}
    sys.stderr.write("ready\n")
    sys.stderr.flush()
    events, t_start = [], time.time()
    def progress():
        return len({e["file"] for e in events}) if a.distinct else len(events)

    while progress() < a.expect and time.time() - t_start < a.timeout:
        for p in paths:
            st = os.stat(p)
            cur = (st.st_mtime_ns, st.st_size)
            if cur != sig[p]:
                now = time.time()
                events.append({"file": rel(root, p), "t_detect": now, "mtime_ns": cur[0], "size": cur[1],
                               "lag_vs_mtime_s": round(now - cur[0] / 1e9, 3)})
                sig[p] = cur
        time.sleep(a.interval)
    out = base("watch", root)
    out.update(events=events, expected=a.expect, seen=progress(), distinct_files_seen=len({e["file"] for e in events}),
               distinct_mode=a.distinct, timed_out=progress() < a.expect,
               poll_interval_s=a.interval, timeout_s=a.timeout)
    return out


def cmd_hostedit_setup(p):
    _root_arg(p)
    p.add_argument("--files", nargs="+", required=True)
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--gap", type=float, default=4.0, help="seconds between edits")
    p.add_argument("--jitter", type=float, default=0.0, help="add uniform 0..JITTER seconds to each gap (breaks phase lock with the poll)")


def cmd_hostedit(a):
    """Append to files with `printf >>` from the shell, recording the time before and after each."""
    root = guard(a.root)
    paths = [inside(root, f) for f in a.files]
    edits = []
    import random
    rng = random.Random()
    gaps = []
    for i in range(a.n):
        gaps.append(a.gap + rng.uniform(0, a.jitter))
        time.sleep(gaps[-1])
        p = paths[i % len(paths)]
        t0 = time.time()
        subprocess.run(["bash", "-c", 'printf "%s\\n" "$1" >> "$2"', "_", f"WSL edit {i + 1} at {t0:.3f}", p], check=True)
        t1 = time.time()
        edits.append({"file": rel(root, p), "t_edit": t0, "t_after": t1, "mtime_ns": os.stat(p).st_mtime_ns})
    out = base("host-edit", root)
    out.update(edits=edits, gaps_s=[round(g, 3) for g in gaps], jitter_s=a.jitter)
    return out


def _load(arg):
    return json.load(open(arg[1:])) if arg.startswith("@") else json.loads(arg)


def cmd_latency_setup(p):
    p.add_argument("--edits-json", required=True, help="host-edit output, JSON text or @file")
    p.add_argument("--watch-json", required=True, help="watch output, JSON text or @file")


def cmd_latency(a):
    edits, watch = _load(a.edits_json)["edits"], _load(a.watch_json)["events"]
    per, used = [], set()
    for e in edits:
        ev = next((w for j, w in enumerate(watch) if j not in used and w["file"] == e["file"] and w["t_detect"] >= e["t_edit"]), None)
        if ev is None:
            per.append({"file": e["file"], "seen": False})
            continue
        used.add(watch.index(ev))
        per.append({"file": e["file"], "seen": True, "latency_s": round(ev["t_detect"] - e["t_edit"], 3),
                    "lag_vs_mtime_s": ev["lag_vs_mtime_s"]})
    lats = [x["latency_s"] for x in per if x["seen"]]
    srt = sorted(lats)
    dist = ({"min": srt[0], "median": round(median(srt), 3), "p95": srt[min(len(srt) - 1, -(-95 * len(srt) // 100) - 1)],
             "max": srt[-1]} if srt else None)
    return {"distribution_s": dist, "measurement": "latency", "per_edit": per, "seen": len(lats), "edits": len(per),
            "max_latency_s": max(lats) if lats else None, "all_within_2s": len(lats) == len(per) and max(lats) <= 2.0,
            "all_within_10s": len(lats) == len(per) and max(lats) <= 10.0,
            "note": "t_edit is WSL wall clock, t_detect is the watcher's wall clock; offset checked separately"}


COMMANDS.update({
    "mounts": (cmd_mounts_setup, cmd_mounts), "scan": (cmd_scan_setup, cmd_scan), "hash": (cmd_hash_setup, cmd_hash),
    "mtime": (cmd_mtime_setup, cmd_mtime), "replace": (cmd_replace_setup, cmd_replace),
    "create": (cmd_create_setup, cmd_create), "case": (cmd_case_setup, cmd_case),
    "illegal": (cmd_illegal_setup, cmd_illegal), "rowrite": (cmd_rowrite_setup, cmd_rowrite),
    "poll": (cmd_poll_setup, cmd_poll), "watch": (cmd_watch_setup, cmd_watch),
    "host-edit": (cmd_hostedit_setup, cmd_hostedit), "latency": (cmd_latency_setup, cmd_latency),
})


def cmd_compare_setup(p):
    p.add_argument("--container-json", required=True, help="watch output from the container, JSON text or @file")
    p.add_argument("--host-json", required=True, help="watch output from the WSL host (fast poll), JSON text or @file")


def cmd_compare(a):
    """Same-clock check: container detect time minus host detect time, per file, in event order."""
    c, h = _load(a.container_json)["events"], _load(a.host_json)["events"]
    per = []
    for f in sorted({e["file"] for e in c} | {e["file"] for e in h}):
        ce = [e for e in c if e["file"] == f]
        he = [e for e in h if e["file"] == f]
        for k in range(max(len(ce), len(he))):
            if k < len(ce) and k < len(he):
                per.append({"file": f, "seen": True, "delay_s": round(ce[k]["t_detect"] - he[k]["t_detect"], 3)})
            else:
                per.append({"file": f, "seen": False})
    d = [x["delay_s"] for x in per if x["seen"]]
    return {"measurement": "compare", "per_file": per, "seen": len(d), "entries": len(per),
            "max_delay_s": max(d) if d else None,
            "all_within_2s": bool(d) and len(d) == len(per) and max(d) <= 2.0,
            "all_within_10s": bool(d) and len(d) == len(per) and max(d) <= 10.0,
            "note": "container and host share the WSL VM clock; the host watcher polls at 0.05 s, so delay carries about 0.05 s plus the container poll interval of error"}


def cmd_skew_setup(p):
    _root_arg(p)
    p.add_argument("--duration", type=float, default=660.0)
    p.add_argument("--interval", type=float, default=1.5)


def _slope(pts):
    n = len(pts)
    mx, my = sum(x for x, _ in pts) / n, sum(y for _, y in pts) / n
    den = sum((x - mx) ** 2 for x, _ in pts)
    return sum((x - mx) * (y - my) for x, y in pts) / den if den else 0.0


def cmd_skew(a):
    """Append to a scratch file from WSL and compare the stamped mtime with the WSL clock."""
    root = guard(a.root)
    d = scratch_dir(root, "_skew")
    path = os.path.join(d, "skew.md")
    t_begin = time.time()
    pts = []
    while time.time() - t_begin < a.duration:
        t0 = time.time()
        with open(path, "a") as fh:
            fh.write(f"{t0:.3f}\n")
        t1 = time.time()
        pts.append((round((t0 + t1) / 2 - t_begin, 3), round(os.stat(path).st_mtime_ns / 1e9 - (t0 + t1) / 2, 4)))
        time.sleep(max(0.0, a.interval - (time.time() - t0)))
    rm_tree(d)
    diffs = [(pts[i][1] - pts[i - 1][1], pts[i][0]) for i in range(1, len(pts))]
    md = median([x for x, _ in diffs]) if diffs else 0.0
    steps = [{"at_s": t, "jump_s": round(x - md, 3)} for x, t in diffs if abs(x - md) > 0.3]
    cuts = [0] + [next(i for i, p in enumerate(pts) if p[0] == s["at_s"]) for s in steps] + [len(pts)]
    segs = [{"from_s": pts[lo][0], "to_s": pts[hi - 1][0], "samples": hi - lo, "slope_s_per_s": round(_slope(pts[lo:hi]), 4),
             "start_skew_s": pts[lo][1], "end_skew_s": pts[hi - 1][1]} for lo, hi in zip(cuts, cuts[1:]) if hi - lo >= 5]
    vals = [v for _, v in pts]
    out = base("skew", root)
    out.update(definition="mtime stamped by Windows minus the WSL clock at the write (positive: Windows ahead)",
               samples=len(pts), duration_s=round(pts[-1][0], 1) if pts else 0, interval_s=a.interval,
               min_s=min(vals), max_s=max(vals), mean_s=round(sum(vals) / len(vals), 4),
               drift_s_per_s_overall=round(_slope(pts), 4), segments=segs, steps=steps, series=pts)
    return out


def cmd_save_setup(p):
    p.add_argument("--dir", required=True, help="results directory (must be the scratch area)")
    p.add_argument("--name", required=True)
    p.add_argument("--text-file", help="wrap this text output instead of reading JSON from stdin")
    p.add_argument("--rc", type=int, default=0)


def cmd_save(a):
    d = guard(a.dir)
    if a.text_file:
        with open(a.text_file, encoding="utf-8", errors="replace") as fh:
            payload = {"measurement": a.name, "rc": a.rc, "output": fh.read()[-4000:]}
    else:
        payload = json.loads(sys.stdin.read())
    with open(os.path.join(d, a.name + ".json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return {"measurement": "save", "saved": a.name + ".json"}


def cmd_assemble_setup(p):
    p.add_argument("--dir", required=True)
    p.add_argument("--out", required=True, help="combined JSON file to write (the raw result file)")


def cmd_assemble(a):
    d = guard(a.dir)
    out_real = os.path.realpath(a.out)
    spikes = os.path.realpath(os.path.join(HERE, "..", "..", "..", "docs", "spikes"))
    if os.path.dirname(out_real) != spikes or not out_real.endswith(".json"):
        refuse(f"--out must be a .json file directly in {spikes}, got {out_real}")
    results = {}
    for f in sorted(os.listdir(d)):
        if f.endswith(".json"):
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                results[f[:-5]] = json.load(fh)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "results": results}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return {"measurement": "assemble", "out": a.out, "entries": sorted(results)}


def _bytes(s):
    import re
    m = re.match(r"([\d.]+)\s*([kKMGT]?i?B)", s.strip())
    mult = {"B": 1, "kB": 1e3, "KB": 1e3, "MB": 1e6, "GB": 1e9, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3}
    return float(m.group(1)) * mult.get(m.group(2), 1) if m else 0.0


def cmd_stats_setup(p):
    p.add_argument("--file", required=True, help="JSON lines from `docker stats --no-stream --format {{json .}}`")


def cmd_stats(a):
    guard(os.path.dirname(os.path.abspath(a.file)))
    rows = [json.loads(line) for line in open(a.file, encoding="utf-8") if line.strip()]
    cpu = [float(r["CPUPerc"].rstrip("%")) for r in rows]
    blk = [(_bytes(r["BlockIO"].split("/")[0]), _bytes(r["BlockIO"].split("/")[1])) for r in rows]
    mem = [_bytes(r["MemUsage"].split("/")[0]) for r in rows]
    return {"measurement": "stats-summary", "samples": len(rows), "cpu_pct_mean": round(sum(cpu) / len(cpu), 3),
            "cpu_pct_peak": max(cpu), "cpu_pct_note": "100% = one full core",
            "block_read_bytes_delta": blk[-1][0] - blk[0][0], "block_write_bytes_delta": blk[-1][1] - blk[0][1],
            "block_io_first": rows[0]["BlockIO"], "block_io_last": rows[-1]["BlockIO"],
            "mem_bytes_mean": round(sum(mem) / len(mem)), "mem_bytes_peak": max(mem)}


COMMANDS.update({"compare": (cmd_compare_setup, cmd_compare), "skew": (cmd_skew_setup, cmd_skew),
                 "save": (cmd_save_setup, cmd_save), "assemble": (cmd_assemble_setup, cmd_assemble),
                 "stats-summary": (cmd_stats_setup, cmd_stats)})


# ---- selftest ----
HERE = os.path.dirname(os.path.abspath(__file__))
SELF = os.path.abspath(__file__)

EXPECTED_FIELDS = {
    "scan": ["files", "cold_ms", "warm_ms", "warm_median_ms", "ms_per_file", "projected_1000_s", "projected_5000_s"],
    "hash": ["files", "bytes", "runs_ms", "median_ms", "ms_per_file", "projected_1000_s", "projected_5000_s"],
    "mtime": ["write1_ns", "write2_ns", "delta_ns", "granularity_ns", "resolution_note"],
    "replace": ["n", "ok", "failures", "leftover_tmp", "per_replace_ms"],
    "create": ["path", "uid", "gid", "mode", "size"],
    "case": ["created_first", "created_second", "distinct_files", "listing"],
    "illegal": ["attempts"],
    "rowrite": ["attempts", "all_erofs"],
    "poll": ["interval_s", "passes", "mean_pass_ms", "max_pass_ms", "over_interval", "ms_per_file_mean"],
    "watch": ["events", "expected", "seen", "timed_out", "distinct_files_seen"],
    "compare": ["per_file", "max_delay_s", "all_within_2s", "all_within_10s"],
    "skew": ["samples", "min_s", "max_s", "drift_s_per_s_overall", "segments", "steps", "series"],
    "host-edit": ["edits", "gaps_s", "jitter_s"],
    "mounts": ["root", "marker_present", "md_files"],
    "save": ["saved"],
    "assemble": ["out", "entries"],
    "stats-summary": ["samples", "cpu_pct_mean", "cpu_pct_peak", "block_read_bytes_delta", "block_write_bytes_delta"],
}


def run_cmd(args, expect_rc=0):
    p = subprocess.run([sys.executable, SELF] + args, capture_output=True, text=True)
    if p.returncode != expect_rc:
        raise AssertionError(f"{args}: rc={p.returncode} stderr={p.stderr.strip()[:300]}")
    return json.loads(p.stdout) if expect_rc == 0 else p


def check_fields(name, out):
    missing = [f for f in EXPECTED_FIELDS[name] if f not in out]
    assert not missing, f"{name}: missing fields {missing}; got {sorted(out)}"
    assert out.get("measurement") == name, f"{name}: bad measurement label {out.get('measurement')}"


def selftest():
    sys.path.insert(0, HERE)
    import shutil
    import gen_corpus
    failures = []

    def case(label, fn):
        try:
            fn()
            print(f"ok    {label}")
        except Exception as exc:  # report every failing case, not just the first
            failures.append(label)
            print(f"FAIL  {label}: {exc}")

    tmp = tempfile.mkdtemp(prefix="sbw-selftest-")
    root = os.path.join(tmp, "Self Test Vault")
    info = gen_corpus.generate(root, count=60, seed=7, allow_any=True)
    again = gen_corpus.generate(os.path.join(tmp, "second"), count=60, seed=7, allow_any=True)
    r = ["--root", root]

    def t_corpus():
        assert info["files"] == 60 and info["bytes"] == again["bytes"], "corpus not deterministic"

    def t_guard():
        outside = tempfile.mkdtemp(prefix="sbw-selftest-outside-")  # no marker, not under prefix
        p = run_cmd(["scan", "--root", outside], expect_rc=2)
        assert "refusing" in p.stderr, p.stderr
        p = run_cmd(["replace", "--root", "/mnt/c/Users", "--n", "1"], expect_rc=2)
        assert "refusing" in p.stderr, p.stderr
        # a symlink under the allowed prefix must not smuggle a path out: checked by realpath
        assert subprocess.run([sys.executable, os.path.join(HERE, "gen_corpus.py"), "--root", outside],
                              capture_output=True, text=True).returncode != 0

    def t_scan():
        o = run_cmd(["scan"] + r + ["--warm", "3"])
        check_fields("scan", o)
        assert o["files"] == 60 and len(o["warm_ms"]) == 3
        assert abs(o["projected_1000_s"] - o["ms_per_file"]) < 1e-3, o  # ms/file x 1000 files = seconds
        assert abs(o["projected_5000_s"] - 5 * o["ms_per_file"]) < 5e-3, o

    def t_hash():
        o = run_cmd(["hash"] + r + ["--runs", "2"])
        check_fields("hash", o)
        assert o["files"] == 60 and o["bytes"] > 60 * 1000

    def t_mtime():
        o = run_cmd(["mtime"] + r)
        check_fields("mtime", o)
        assert o["delta_ns"] > 0

    def t_replace():
        o = run_cmd(["replace"] + r + ["--n", "10"])
        check_fields("replace", o)
        assert o["ok"] == 10 and o["failures"] == 0 and o["leftover_tmp"] == 0, o
        target = os.path.join(root, "Projects", os.listdir(os.path.join(root, "Projects"))[0])
        if os.path.isdir(target):
            target = next(os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.endswith(".md"))
        o = run_cmd(["replace"] + r + ["--target", target])
        check_fields("replace", o)
        assert o["ok"] == 1 and o["mode"] == "target", o
        last = open(target).read().splitlines()[-1]
        assert last.startswith("REPLACED "), last  # visible plain line, not an HTML comment
        # --dir with --seconds: runs in the named folder, leaves it, removes its own file
        os.makedirs(os.path.join(root, "Loop Dir"), exist_ok=True)
        o = run_cmd(["replace"] + r + ["--dir", "Loop Dir", "--seconds", "1", "--pause-ms", "50"])
        assert o["ok"] >= 5 and o["failures"] == 0 and o["n"] == o["ok"] and o["dir"] == "Loop Dir", o
        assert os.path.isdir(os.path.join(root, "Loop Dir")) and not os.path.exists(os.path.join(root, "Loop Dir", "m6-loop.md"))
        p = run_cmd(["replace"] + r + ["--dir", "../escape", "--n", "1"], expect_rc=2)
        assert "refusing" in p.stderr, p.stderr

    def t_create():
        o = run_cmd(["create"] + r)
        check_fields("create", o)
        assert o["uid"] == os.getuid() and o["size"] > 0

    def t_case():
        o = run_cmd(["case"] + r)
        check_fields("case", o)

    def t_illegal():
        o = run_cmd(["illegal"] + r)
        check_fields("illegal", o)
        assert {a["name"] for a in o["attempts"]} == {"a:b.md", "a?b.md"}
        o = run_cmd(["illegal"] + r + ["--keep"])
        assert o["kept"] and os.path.isdir(os.path.join(root, "_m11"))
        shutil.rmtree(os.path.join(root, "_m11"))

    def t_rowrite():
        # a local temp dir is writable, so this must report a write that succeeded (not EROFS)
        o = run_cmd(["rowrite"] + r)
        check_fields("rowrite", o)
        assert o["all_erofs"] is False
        assert not [f for f in os.listdir(root) if f.startswith(".sbw-ro-probe")], "probe file left behind"

    def t_poll():
        o = run_cmd(["poll"] + r + ["--interval", "0.2", "--duration", "1"])
        check_fields("poll", o)
        assert o["passes"] >= 3 and o["over_interval"] == 0

    def t_watch_and_hostedit():
        files = [os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.endswith(".md")][:2]
        out = {}

        def watch():
            out["w"] = run_cmd(["watch"] + r + ["--files"] + files + ["--expect", "2", "--timeout", "15", "--interval", "0.1"])

        th = threading.Thread(target=watch)
        th.start()
        time.sleep(1.0)
        e = run_cmd(["host-edit"] + r + ["--files"] + files + ["--n", "2", "--gap", "0.5"])
        th.join()
        check_fields("host-edit", e)
        check_fields("watch", out["w"])
        assert out["w"]["seen"] == 2 and not out["w"]["timed_out"], out["w"]
        lat = run_cmd(["latency", "--edits-json", json.dumps(e), "--watch-json", json.dumps(out["w"])])
        assert lat["measurement"] == "latency" and len(lat["per_edit"]) == 2 and "all_within_2s" in lat, lat


    def t_save_assemble_stats():
        res = os.path.join(root, "_results")
        os.makedirs(res)
        shutil.copy(os.path.join(root, MARKER), res)  # results dir needs the marker outside /mnt/d/sbw-spike/
        p = subprocess.run([sys.executable, SELF, "save", "--dir", res, "--name", "M1"], input='{"a": 1}', capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        check_fields("save", json.loads(p.stdout))
        txt = os.path.join(res, "o.txt")
        open(txt, "w").write("hello")
        check_fields("save", run_cmd(["save", "--dir", res, "--name", "M0", "--text-file", txt, "--rc", "0"]))
        out_json = os.path.join(HERE, "..", "..", "..", "docs", "spikes", "selftest-tmp2.json")
        try:
            o = run_cmd(["assemble", "--dir", res, "--out", out_json])
            check_fields("assemble", o)
            assert o["entries"] == ["M0", "M1"] and json.load(open(out_json))["results"]["M1"] == {"a": 1}
        finally:
            if os.path.exists(out_json):
                os.unlink(out_json)
        sf = os.path.join(res, "stats.jsonl")
        with open(sf, "w") as fh:
            fh.write(json.dumps({"CPUPerc": "1.50%", "BlockIO": "1MB / 0B", "MemUsage": "10MiB / 1GiB"}) + "\n")
            fh.write(json.dumps({"CPUPerc": "3.50%", "BlockIO": "3MB / 2kB", "MemUsage": "12MiB / 1GiB"}) + "\n")
        s = run_cmd(["stats-summary", "--file", sf])
        check_fields("stats-summary", s)
        assert s["cpu_pct_mean"] == 2.5 and s["block_read_bytes_delta"] == 2e6 and s["block_write_bytes_delta"] == 2000, s

    def t_distinct_jitter_compare_skew():
        files = [os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.endswith(".md")][2:4]
        out = {}
        th = threading.Thread(target=lambda: out.update(w=run_cmd(
            ["watch"] + r + ["--files"] + files + ["--expect", "2", "--distinct", "--timeout", "15", "--interval", "0.05"])))
        th.start()
        time.sleep(1.0)
        e = run_cmd(["host-edit"] + r + ["--files"] + files + ["--n", "4", "--gap", "0.4", "--jitter", "0.2"])
        th.join()
        assert out["w"]["distinct_files_seen"] == 2 and out["w"]["seen"] == 2 and not out["w"]["timed_out"], out["w"]
        assert len(e["gaps_s"]) == 4 and all(0.4 <= g <= 0.6 + 1e-6 for g in e["gaps_s"]) and len(set(e["gaps_s"])) > 1, e["gaps_s"]
        # the same file edited twice is two events but one distinct file: --distinct must keep waiting
        ev = out["w"]["events"]
        c = {"events": [dict(x, t_detect=x["t_detect"] + 0.5) for x in ev]}
        o = run_cmd(["compare", "--container-json", json.dumps(c), "--host-json", json.dumps({"events": ev})])
        check_fields("compare", o)
        assert o["all_within_2s"] and abs(o["max_delay_s"] - 0.5) < 1e-6, o
        late = {"events": [dict(x, t_detect=x["t_detect"] + 3.0) for x in ev]}
        o = run_cmd(["compare", "--container-json", json.dumps(late), "--host-json", json.dumps({"events": ev})])
        assert not o["all_within_2s"] and o["all_within_10s"], o
        o = run_cmd(["skew"] + r + ["--duration", "3", "--interval", "0.5"])
        check_fields("skew", o)
        assert o["samples"] >= 4 and o["min_s"] <= o["max_s"], o
        assert not os.path.exists(os.path.join(root, "_skew"))

    def t_assemble_guard():
        res = os.path.join(root, "_results2")
        os.makedirs(res)
        shutil.copy(os.path.join(root, MARKER), res)
        for bad in (os.path.join(tmp, "x.json"), os.path.join(HERE, "x.json"), os.path.join(HERE, "..", "..", "..", "docs", "x.json")):
            p = run_cmd(["assemble", "--dir", res, "--out", bad], expect_rc=2)
            assert "refusing" in p.stderr, p.stderr
        good = os.path.join(HERE, "..", "..", "..", "docs", "spikes", "selftest-tmp.json")
        try:
            check_fields("assemble", run_cmd(["assemble", "--dir", res, "--out", good]))
        finally:
            if os.path.exists(good):
                os.unlink(good)

    def t_run_sh_guard():
        if not shutil.which("docker"):
            return
        bad = os.path.join(tmp, "bad.env")
        open(bad, "w").write('SPIKE_PATH="/tmp/not-the-scratch-folder"\n')
        p = subprocess.run(["bash", os.path.join(HERE, "run.sh"), "up"], capture_output=True, text=True,
                           env=dict(os.environ, ENVFILE=bad))
        assert p.returncode == 1 and "refusing" in p.stderr, (p.returncode, p.stderr[-300:])

    def t_mounts():
        o = run_cmd(["mounts"] + r)
        check_fields("mounts", o)
        assert o["marker_present"] and o["md_files"] >= 60, o

    for label, fn in [("corpus deterministic", t_corpus), ("root guard refuses", t_guard), ("scan", t_scan),
                      ("hash", t_hash), ("mtime", t_mtime), ("replace", t_replace), ("create", t_create),
                      ("case", t_case), ("illegal", t_illegal), ("rowrite", t_rowrite), ("poll", t_poll),
                      ("watch + host-edit + latency", t_watch_and_hostedit), ("mounts", t_mounts), ("save + assemble + stats-summary", t_save_assemble_stats),
                      ("watch --distinct, jitter, compare, skew", t_distinct_jitter_compare_skew),
                      ("assemble --out guard", t_assemble_guard), ("run.sh up guard", t_run_sh_guard)]:
        case(label, fn)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{17 - len(failures)}/17 passed")
    return 1 if failures else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, (setup, _fn) in COMMANDS.items():
        setup(sub.add_parser(name))
    a = ap.parse_args(argv)
    out = COMMANDS[a.cmd][1](a)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

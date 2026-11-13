#!/usr/bin/env python3
"""Independent QA matrix for `lore init` (route + optional features model).

Reads qa/init-expectations.yaml (the oracle), runs the real CLI in temp
directories and checks the output against the oracle.  No AI, no lore imports.

    python scripts/qa_init_matrix.py                    # 72 fixed x agents + samples + switches + migration
    python scripts/qa_init_matrix.py --only cli.mem      # substring / regex filter on scenario names
    python scripts/qa_init_matrix.py --random 20 --seed 7
    python scripts/qa_init_matrix.py --jobs 8 --keep --report qa/init-results.md

Severity: findings of oracle rows carrying `jc:` are WARN (judgement call);
everything else is FAIL.  Exit code 1 when any FAIL.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import itertools
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required (run with the project venv: .venv/bin/python scripts/qa_init_matrix.py)")

ROOT = Path(__file__).resolve().parent.parent
ORACLE_PATH = ROOT / "qa" / "init-expectations.yaml"
SCRATCH = Path("/tmp/claude-1000/-home-kk-camelot/cb26d575-1690-45de-8018-5f1bfd1e0213/scratchpad")

# ---------------------------------------------------------------------------
# Flag construction -- ONE table, adapt here if `lore init --help` differs.
# ---------------------------------------------------------------------------
ROUTE_FLAG = "--route"
BOOL_FLAGS = {
    "memory": "--memory",
    "memory_search": "--memory-search",
    "memory_index": "--memory-index",
    "memory_graph": "--memory-graph",
    "quests": "--quests",
    "watchers": "--watchers",
}
AGENT_FLAG = "--agent"
COMMON_FLAGS = ["--yes"]
_STYLE: list[str] = []  # cached: "pair" (--x/--no-x) or "value" (--x yes|no)

ANSWERS = ["route", "memory", "memory_search", "memory_index", "memory_graph", "quests", "watchers"]


def lore_cmd(args: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    py = ROOT / ".venv" / "bin" / "python"
    exe = str(py) if py.exists() else sys.executable
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), NO_COLOR="1", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([exe, "-m", "lore", *args], cwd=cwd, env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=timeout)


def flag_style() -> str:
    if not _STYLE:
        r = lore_cmd(["init", "--help"], Path(tempfile.gettempdir()))
        _STYLE.append("pair" if "--no-memory" in (r.stdout + r.stderr) else "value")
    return _STYLE[0]


def answer_flags(p: dict) -> list[str]:
    out = [ROUTE_FLAG, p["route"]]
    for k, flag in BOOL_FLAGS.items():
        if k in ("memory_search", "memory_index", "memory_graph") and not p["memory"]:
            continue
        v = p[k]
        if flag_style() == "pair":
            out.append(flag if v else "--no-" + flag[2:])
        else:
            out += [flag, "yes" if v else "no"]
    return out


def init_args(p: dict | None, agents: list[str] | None) -> list[str]:
    a = ["init", *COMMON_FLAGS]
    if agents:
        a += [AGENT_FLAG, *agents]
    if p:
        a += answer_flags(p)
    return a


# ---------------------------------------------------------------------------
# Oracle
# ---------------------------------------------------------------------------
class Oracle:
    def __init__(self, path: Path = ORACLE_PATH):
        self.d = yaml.safe_load(path.read_text())

    def env(self, p: dict) -> dict:
        e = dict(p)
        for k, expr in self.d["derived"].items():
            e[k] = self.ev(expr, e)
        return e

    @staticmethod
    def ev(expr: str, env: dict) -> bool:
        return bool(eval(expr, {"__builtins__": {}}, env))  # trusted oracle file

    def normalise(self, p: dict) -> dict:
        q = {k: v["default"] for k, v in self.d["answers"].items()}
        q.update(p)
        if not q["memory"]:
            q["memory_search"] = q["memory_index"] = q["memory_graph"] = False
        return q


def sev(row: dict) -> str:
    return "WARN" if row.get("jc") else "FAIL"


class Findings:
    def __init__(self):
        self.items: list[tuple[str, str, str]] = []  # (sev, check, msg)

    def add(self, check: str, msg: str, row: dict | None = None, severity: str | None = None):
        self.items.append((severity or (sev(row) if row else "FAIL"), check, msg + (f" [jc{row['jc']}]" if row and row.get("jc") else "")))

    @property
    def fails(self):
        return [i for i in self.items if i[0] == "FAIL"]


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------
def tree_files(base: Path) -> set[str]:
    if not base.is_dir():
        return set()
    return {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}


def defaults_tree(oracle: Oracle, key: str) -> list[str]:
    return sorted(tree_files(ROOT / oracle.d["seeds"][key]["from"]))


def hash_tree(proj: Path) -> dict[str, str]:
    out = {}
    for p in proj.rglob("*"):
        if p.is_file():
            rel = p.relative_to(proj).as_posix()
            if rel in (".lore/lore.db", ".lore/.install-manifest.json") or rel.startswith(".lore/reports/") or "-journal" in rel or rel.endswith((".db-wal", ".db-shm")):
                continue
            out[rel] = hashlib.sha1(p.read_bytes()).hexdigest()
    return out


def agent_layout(oracle: Oracle, agents: list[str]):
    ag = oracle.d["agents"]
    instr = [ag[a]["instruction_file"] for a in agents if ag[a]["instruction_file"]]
    skill_dirs = sorted({ag[a]["skills_dir"] for a in agents})
    return instr, skill_dirs


def read(p: Path) -> str:
    return p.read_text(errors="replace") if p.is_file() else ""


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`([^`\n]+)`")


def code_regions(text: str) -> list[str]:
    regions = [m.group(0) for m in FENCE.finditer(text)]
    rest = FENCE.sub("", text)
    regions += [m.group(1) for m in INLINE.finditer(rest)]
    return regions


WORD = re.compile(r"^[a-z][a-z-]*$")


def extract_phrases(text: str, groups: list[str]) -> set[str]:
    phrases: set[str] = set()
    for region in code_regions(text):
        for line in region.splitlines():
            for m in re.finditer(r"(?<![\w./\-])lore(?=[ \t])", line):
                toks = [t.strip(".,;:)(\"'") for t in line[m.end():].split()]
                toks = [t for t in toks if t]
                if not toks:
                    continue
                t1 = toks[0]
                if t1.startswith("--"):
                    phrases.add(f"lore {t1}")
                    continue
                if not WORD.match(t1):
                    continue
                if t1 == "health":
                    scopes = []
                    if "--scope" in toks:
                        for t in toks[toks.index("--scope") + 1:]:
                            if t.startswith("-") or not WORD.match(t):
                                break
                            scopes.append(t)
                    if scopes:
                        phrases.update(f"lore health --scope {s}" for s in scopes)
                    else:
                        phrases.add("lore health")
                elif t1 in groups:
                    t2 = toks[1] if len(toks) > 1 else ""
                    subs = [s for s in re.split(r"[|/]", t2) if WORD.match(s)]
                    if subs:
                        phrases.update(f"lore {t1} {s}" for s in subs)
                    else:
                        phrases.add(f"lore {t1}")
                else:
                    phrases.add(f"lore {t1}")
    return phrases


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------
def check_project(oracle: Oracle, proj: Path, p: dict, agents: list[str], f: Findings, *, health: bool = True, switched: bool = False):
    d = oracle.d
    e = oracle.env(p)
    instr_files, skill_dirs = agent_layout(oracle, agents)

    # 1. fixed files
    for rel in d["fixed_files"]["always"]:
        if not (proj / rel).is_file():
            f.add("fixed-files", f"missing {rel}")
    lore_dir = proj / ".lore"
    if lore_dir.is_dir():
        for child in sorted(lore_dir.iterdir()):
            if child.name not in d["lore_dir_entries"]:
                f.add("fixed-files", f"unexpected entry .lore/{child.name}", severity="WARN")

    # 2. seeds
    exp_seeds: dict[str, str] = {}
    sd = d["seeds"]
    for key in ("doctrines", "watchers"):
        if oracle.ev(sd[key]["when"], e):
            for rel in defaults_tree(oracle, key):
                exp_seeds[f"{sd[key]['to']}/{rel}"] = key
    art = sd["artifacts"]
    art_jc: dict[str, dict] = {}
    for rel in defaults_tree(oracle, "artifacts"):
        rule = next((r for r in art["rules"] if fnmatch.fnmatch(rel, r["glob"])), None)
        if rule is None:
            f.add("seeds", f"unclassified shipped artifact {rel} (add a rule to the oracle)")
            continue
        art_jc[rel] = rule
        if oracle.ev(rule["when"], e):
            exp_seeds[f"{art['to']}/{rel}"] = f"artifacts[{rule['owner']}]"
    mem = sd["memory"]
    if oracle.ev(mem["when"], e):
        for rel in mem["must_exist"]:
            if not (proj / rel).exists():
                f.add("seeds", f"memory seed missing {rel}")
    else:
        for rel in mem["must_not_exist_when_off"]:
            if (proj / rel).exists():
                f.add("seeds", f"memory off but {rel} exists", severity="WARN" if switched else None)
    for key, root in (("doctrines", sd["doctrines"]["to"]), ("watchers", sd["watchers"]["to"]), ("artifacts", art["to"])):
        actual = {f"{root}/{r}" for r in tree_files(proj / root)}
        exp = {k for k in exp_seeds if k.startswith(root + "/")}
        for missing in sorted(exp - actual):
            rel = missing[len(root) + 1:]
            row = art_jc.get(rel, {}) if key == "artifacts" else {}
            f.add("seeds", f"missing seed {missing} (owner {exp_seeds[missing]})", row)
        for extra in sorted(actual - exp):
            rel = extra[len(root) + 1:]
            row = art_jc.get(rel, {}) if key == "artifacts" else {}
            f.add("seeds", f"seed must not exist: {extra}", row)

    # 3. skills
    exp_skills = {s["id"]: s for s in d["skills"] if oracle.ev(s["installed_when"], e)}
    all_ids = [s["id"] for s in d["skills"]]
    skill_texts: dict[str, str] = {}
    for sdir in skill_dirs:
        base = proj / sdir
        actual = {c.name for c in base.iterdir() if c.is_dir()} if base.is_dir() else set()
        for sid in sorted(set(exp_skills) - actual):
            f.add("skills", f"{sdir}: missing skill {sid}", exp_skills[sid])
        for sid in sorted(actual - set(exp_skills)):
            row = next((s for s in d["skills"] if s["id"] == sid), {})
            f.add("skills", f"{sdir}: skill must not exist: {sid}" + ("" if sid in all_ids else " (unknown id)"), row)
        for sid in sorted(actual & set(exp_skills)):
            sk = base / sid / "SKILL.md"
            text = read(sk)
            if not text:
                f.add("skills", f"{sdir}/{sid}: SKILL.md missing/empty")
                continue
            skill_texts[f"{sdir}/{sid}/SKILL.md"] = text
            fm = re.match(r"---\n(.*?)\n---", text, re.S)
            try:
                meta = yaml.safe_load(fm.group(1)) if fm else None
            except yaml.YAMLError:
                meta = None
            if not isinstance(meta, dict) or meta.get("name") != sid or not str(meta.get("description", "")).strip():
                f.add("skills", f"{sdir}/{sid}: bad frontmatter (name must equal dir, description non-empty)")
            lines = len(text.splitlines())
            cap = d["sizes"]["skill_exceptions"].get(sid, d["sizes"]["skill_max_lines"])
            if lines > cap:
                f.add("skill-size", f"{sdir}/{sid}/SKILL.md has {lines} lines (cap {cap})")
            refs = tree_files(base / sid / "references") if (base / sid / "references").exists() else set()
            allowed = set(d["references"]["allowed"].get(sid, []))
            for r in sorted(refs):
                rel = f"references/{r}"
                if rel not in allowed:
                    f.add("references", f"{sdir}/{sid}/{rel}: references not allowed for this skill")
                else:
                    skill_texts[f"{sdir}/{sid}/{rel}"] = read(base / sid / "references" / r)
            for link in set(re.findall(r"references/[\w.-]+\.md", text)):
                if not (base / sid / link).is_file():
                    f.add("references", f"{sdir}/{sid}: links missing {link}")

    # 4. instruction files
    m = d["markers"]
    blocks: dict[str, str] = {}
    for rel in instr_files:
        text = read(proj / rel)
        if not text:
            f.add("instruction", f"{rel}: missing/empty")
            continue
        b, e_ = text.find(m["begin"]), text.find(m["end"])
        if b < 0 or e_ < 0:
            f.add("instruction", f"{rel}: lore markers missing")
            block = text
        else:
            block = text[b:e_ + len(m["end"])]
        nl = len(block.splitlines())
        if nl > d["sizes"]["instruction_block_max_lines"]:
            f.add("instruction", f"{rel}: block has {nl} lines (max {d['sizes']['instruction_block_max_lines']})")
        if "lore health" not in block:
            f.add("instruction", f"{rel}: does not mention `lore health`")
        blocks[rel] = block
    extra_docs = {x: read(proj / x) for x in d["extra_docs"] if (proj / x).is_file()}

    # 5. commands, forbidden text, term leak, placeholders, skill refs, paths
    instruction_scope = {**blocks, **extra_docs}
    scope = {**instruction_scope, **skill_texts}
    rows = {c["phrase"]: c for c in d["commands"]}
    ignore = set(d.get("ignore_phrases", []))
    for name, text in scope.items():
        for ph in sorted(extract_phrases(text, d["groups"])):
            if ph in ignore:
                continue
            row = rows.get(ph)
            if row is None:
                pref = [r for r in d["commands"] if r["phrase"].startswith(ph + " ")]
                if pref and ph.split()[1] in d["groups"]:  # bare group mention (e.g. `lore codex --help`)
                    continue
                f.add("commands", f"{name}: `{ph}` is not a known lore command phrase")
            elif not oracle.ev(row["when"], e):
                f.add("commands", f"{name}: `{ph}` not granted (needs {row['when']})", row)
        for st in d.get("skill_text", []):
            if not name.endswith(f"/{st['skill']}/SKILL.md") or not oracle.ev(st["when"], e):
                continue
            for rx in st.get("absent", []):
                if re.search(rx, text):
                    f.add("skill-text", f"{name}: {st['why']} (found /{rx}/)")
            for rx in st.get("present", []):
                if not re.search(rx, text):
                    f.add("skill-text", f"{name}: {st['why']} (missing /{rx}/)")
        for ft in d["forbidden_text"]:
            if oracle.ev(ft["when"], e) and re.search(ft["regex"], text):
                f.add("forbidden-text", f"{name}: {ft['why']} (/{ft['regex']}/)")
        for tl in d["term_leak"]:
            if oracle.ev(tl["when"], e):
                for w in tl["words"]:
                    if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text):
                        f.add("term-leak", f"{name}: mentions '{w}' while the feature is off",
                              severity="FAIL" if name in instruction_scope else "WARN")
        for ph in d["placeholders"]:
            if ph in text:
                f.add("placeholders", f"{name}: contains '{ph}'")
        for sid in all_ids:
            if sid not in exp_skills and re.search(rf"(?<![\w-]){re.escape(sid)}(?![\w-])", text):
                f.add("skill-refs", f"{name}: references skill '{sid}' which is not installed")
        for m_ in re.finditer(r"(\.(?:lore|claude/skills)/[A-Za-z0-9_./-]*)([<*{\[]?)", text):
            path, nxt = m_.group(1).rstrip(".,"), m_.group(2)
            if nxt:
                path = path.rstrip("/") if path.endswith("/") else path.rsplit("/", 1)[0]
            else:
                path = path.rstrip("/")
            if any(path == o or path.startswith(o + "/") for o in d["on_demand_paths"]):
                continue
            if not (proj / path).exists():
                parts = path.split("/")
                top = "/".join(parts[:2])
                under_user_root = len(parts) > 2 and parts[1] in d["user_roots"] and not (len(parts) > 2 and parts[2] == "default")
                if (proj / top).exists() and under_user_root:
                    f.add("paths", f"{name}: mentions {path} (not present; example path?)", severity="WARN")
                elif path.startswith(".claude/skills") and "claude" not in agents:
                    f.add("paths", f"{name}: mentions {path} (claude is not a selected agent)", severity="WARN")
                else:
                    f.add("paths", f"{name}: mentions {path} which does not exist")
    # instruction file must teach validate even in the extra docs? (only the block is required above)

    # 6. config
    cfg_path = proj / ".lore" / "config.toml"
    if cfg_path.is_file():
        try:
            cfg = tomllib.loads(cfg_path.read_text())
        except tomllib.TOMLDecodeError as ex:
            cfg = {}
            f.add("config", f"config.toml unparsable: {ex}")
        for k in ANSWERS:
            if k in ("memory_search", "memory_index", "memory_graph") and not p["memory"]:
                continue
            key = "init-" + k.replace("_", "-")
            if cfg.get(key) != p[k]:
                f.add("config", f"{key} = {cfg.get(key)!r}, expected {p[k]!r}")

    # 7. health
    if health:
        for args in (["health"], ["health", "--scope", "skills"]):
            r = lore_cmd(args, proj)
            if r.returncode != 0:
                tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
                f.add("health", f"`lore {' '.join(args)}` exit {r.returncode}: {' | '.join(tail)[:300]}")


def run_init(proj: Path, p: dict | None, agents: list[str] | None, f: Findings, label: str = "init") -> subprocess.CompletedProcess:
    r = lore_cmd(init_args(p, agents), proj)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()[-4:]
        f.add("init-exit", f"{label}: exit {r.returncode}: {' | '.join(tail)[:400]}")
    return r


def check_idempotent(proj: Path, p: dict | None, agents: list[str] | None, f: Findings):
    before = hash_tree(proj)
    r = lore_cmd(init_args(p, agents), proj)
    if r.returncode != 0:
        f.add("idempotent", f"second run exit {r.returncode}: {(r.stdout + r.stderr).strip()[-300:]}")
        return
    after = hash_tree(proj)
    changed = sorted({k for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    if changed:
        f.add("idempotent", f"second run changed {len(changed)} file(s): {', '.join(changed[:5])}")
    noisy = [ln.strip() for ln in r.stdout.splitlines() if re.match(r"\s*(Created|Updated|Replaced|Removed)\b", ln)]
    if noisy:
        f.add("idempotent", f"second run reports changes: {noisy[0]} (+{len(noisy) - 1})", severity="WARN")


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
def pname(p: dict) -> str:
    mem = "m-" + ("".join(c for c, k in (("S", "memory_search"), ("I", "memory_index"), ("G", "memory_graph")) if p[k]) or "-") if p["memory"] else "m-off"
    return f"{p['route']}.{mem}.{'q' if p['quests'] else 'noq'}.{'w' if p['watchers'] else 'now'}"


def all_valid_profiles(oracle: Oracle) -> list[dict]:
    out = []
    for route, quests, watchers in itertools.product(("harness", "cli"), (True, False), (True, False)):
        out.append(oracle.normalise(dict(route=route, memory=False, quests=quests, watchers=watchers)))
        for s, i, g in itertools.product((True, False), repeat=3):
            out.append(oracle.normalise(dict(route=route, memory=True, memory_search=s, memory_index=i, memory_graph=g,
                                             quests=quests, watchers=watchers)))
    return out


def build_scenarios(oracle: Oracle, args) -> list[dict]:
    sc = oracle.d["scenarios"]
    out: list[dict] = []
    base = sc["fixed"]["agents_base"]
    for p in all_valid_profiles(oracle):
        out.append(dict(kind="profile", name=f"{pname(p)}@{'+'.join(base)}", profile=p, agents=base))
    for sel in sc["agent_samples"]["selections"]:
        for raw in sc["agent_samples"]["profiles"]:
            p = oracle.normalise(raw)
            out.append(dict(kind="profile", name=f"{pname(p)}@{'+'.join(sel)}", profile=p, agents=sel))
    h = sc["headless"]
    out.append(dict(kind="headless", name="headless-default", profile=oracle.normalise(h["expect"]), agents=h["agent"]))
    for sw in sc["switches"]:
        out.append(dict(kind="switch", name=f"switch.{sw['id']}", a=oracle.normalise(sw["a"]), b=oracle.normalise(sw["b"]), agents=base))
    for inv in sc["invalid"]:
        out.append(dict(kind="invalid", name=f"invalid.{inv['id']}", inv=inv))
    for grp in ("interim15", "legacy"):
        for c in oracle.d["migration"][grp]:
            out.append(dict(kind="migration", name=f"migrate.{c['id']}", case=c, profile=oracle.normalise(c["expect"]), agents=["claude"]))
    if args.random:
        rng = random.Random(args.seed)
        sels = [["claude"], ["agents-md"], ["none"], ["claude", "agents-md"], ["claude", "gemini"]]
        pool = all_valid_profiles(oracle)
        for i in range(args.random):
            p, sel = rng.choice(pool), rng.choice(sels)
            out.append(dict(kind="profile", name=f"rand{args.seed}-{i}.{pname(p)}@{'+'.join(sel)}", profile=p, agents=sel))
    if args.only:
        rx = re.compile(args.only)
        out = [s for s in out if rx.search(s["name"])]
    return out


def toml_val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(toml_val(x) for x in v) + "]"
    return '"' + str(v) + '"'


def run_scenario(oracle: Oracle, s: dict, tmp_root: Path, keep: bool) -> tuple[dict, Findings, Path]:
    f = Findings()
    proj = Path(tempfile.mkdtemp(prefix="s-", dir=tmp_root))
    try:
        kind = s["kind"]
        if kind == "profile":
            run_init(proj, s["profile"], s["agents"], f)
            check_project(oracle, proj, s["profile"], s["agents"], f)
            check_idempotent(proj, s["profile"], s["agents"], f)
        elif kind == "headless":
            run_init(proj, None, s["agents"], f)
            check_project(oracle, proj, s["profile"], s["agents"], f)
            check_idempotent(proj, None, s["agents"], f)
        elif kind == "switch":
            run_init(proj, s["a"], s["agents"], f, "init A")
            run_init(proj, s["b"], s["agents"], f, "init B")
            check_project(oracle, proj, s["b"], s["agents"], f, switched=True)
            fresh = Path(tempfile.mkdtemp(prefix="fresh-", dir=tmp_root))
            try:
                run_init(fresh, s["b"], s["agents"], Findings())
                hs, hf = hash_tree(proj), hash_tree(fresh)
                allowed = oracle.d["scenarios"]["switch_leftovers_allowed"]
                for k in sorted(hs.keys() - hf.keys()):
                    if any(k.startswith(pfx + "/") for pfx in allowed["prefixes"]):
                        f.add("switch", f"leftover after switch (user-owned memory?): {k}", severity="WARN")
                    else:
                        f.add("switch", f"leftover of the dropped part: {k}")
                for k in sorted(hf.keys() - hs.keys()):
                    f.add("switch", f"missing after switch (present in fresh B): {k}")
                for k in sorted(hs.keys() & hf.keys()):
                    if hs[k] != hf[k]:
                        f.add("switch", f"content differs from fresh B: {k}")
            finally:
                shutil.rmtree(fresh, ignore_errors=True)
        elif kind == "invalid":
            r = lore_cmd(["init", *COMMON_FLAGS, *s["inv"]["args"]], proj)
            if r.returncode != s["inv"]["exit"]:
                f.add("invalid", f"expected exit {s['inv']['exit']}, got {r.returncode}")
            written = tree_files(proj / ".lore")
            if written:
                f.add("invalid", f"wrote {len(written)} file(s) under .lore/ despite the error")
        elif kind == "migration":
            c = s["case"]
            (proj / ".lore").mkdir()
            cfg = {"init-agents": s["agents"], **c["config"]}
            (proj / ".lore" / "config.toml").write_text("".join(f"{k} = {toml_val(v)}\n" for k, v in cfg.items()))
            row = {"jc": c["jc"]} if c.get("jc") else None
            r = run_init(proj, None, None, f)
            sub = Findings()
            if r.returncode == 0:
                check_project(oracle, proj, s["profile"], s["agents"], sub)
                try:
                    now = tomllib.loads(read(proj / ".lore" / "config.toml"))
                except tomllib.TOMLDecodeError:
                    now = {}
                stale = [k for k in now if k in c["config"] or k in ("init-access-mode", "init-skill-families")
                         or re.fullmatch(r"init-(memory|doctrines|artifacts|watchers)-(read|write|validate)", k)]
                if stale:
                    sub.add("migration", f"retired keys still in config.toml: {', '.join(stale)}", severity="WARN")
                check_idempotent(proj, None, None, sub)
            for sev_, chk, msg in sub.items:
                f.items.append((sev_ if not row or sev_ == "WARN" else "WARN", "migration:" + chk, msg + (f" [jc{c['jc']}]" if row else "")))
        return s, f, proj
    except Exception as ex:  # noqa: BLE001
        f.add("crash", f"{type(ex).__name__}: {ex}")
        return s, f, proj
    finally:
        if not keep:
            shutil.rmtree(proj, ignore_errors=True)


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="regex on scenario names")
    ap.add_argument("--random", type=int, default=0, help="add N seeded random profiles")
    ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 4))
    ap.add_argument("--keep", action="store_true", help="keep the temp project dirs")
    ap.add_argument("--list", action="store_true", help="list scenario names and exit")
    ap.add_argument("--report", help="write a markdown results summary to this path")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every finding per scenario")
    args = ap.parse_args(argv)

    oracle = Oracle()
    scenarios = build_scenarios(oracle, args)
    if args.list:
        print("\n".join(s["name"] for s in scenarios))
        return 0
    tmp_root = Path(tempfile.mkdtemp(prefix="qa-init-", dir=SCRATCH if SCRATCH.is_dir() else None))
    flag_style()
    print(f"{len(scenarios)} scenarios, jobs={args.jobs}, seed={args.seed}, flag style={flag_style()}, tmp={tmp_root}")
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for s, f, proj in ex.map(lambda sc_: run_scenario(oracle, sc_, tmp_root, args.keep), scenarios):
            nfail, nwarn = len(f.fails), len(f.items) - len(f.fails)
            status = "FAIL" if nfail else ("WARN" if nwarn else "PASS")
            print(f"{status} {s['name']}" + (f"  ({nfail} fail, {nwarn} warn)" if f.items else "") + (f"  {proj}" if args.keep else ""))
            if args.verbose:
                for it in f.items:
                    print(f"      {it[0]} {it[1]}: {it[2]}")
            results.append((s, f))
    if not args.keep:
        shutil.rmtree(tmp_root, ignore_errors=True)

    groups: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for s, f in results:
        for sv, chk, msg in f.items:
            groups[(sv, chk)].append((s["name"], msg))
    n_fail = sum(1 for _, f in results if f.fails)
    n_warn = sum(1 for _, f in results if f.items and not f.fails)
    summary = [f"scenarios: {len(results)}  pass: {len(results) - n_fail - n_warn}  warn-only: {n_warn}  fail: {n_fail}"]
    for (sv, chk), items in sorted(groups.items(), key=lambda kv: (kv[0][0] != "FAIL", kv[0][1])):
        scen = sorted({n for n, _ in items})
        msgs: dict[str, int] = defaultdict(int)
        for _, m_ in items:
            msgs[re.sub(r"^\S+: ", "", m_)] += 1
        summary.append(f"\n[{sv}] {chk}: {len(items)} finding(s) in {len(scen)} scenario(s); e.g. {scen[0]}")
        for m_, n in sorted(msgs.items(), key=lambda kv: -kv[1])[:6]:
            summary.append(f"    {n:>4}x {m_[:200]}")
    print("\n" + "\n".join(summary))
    if args.report:
        Path(args.report).write_text("```\n" + "\n".join(summary) + "\n```\n")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

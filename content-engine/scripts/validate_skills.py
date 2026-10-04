#!/usr/bin/env python3
"""Check content-engine skills: frontmatter, required sections, referenced files/skills exist."""
import re, sys, pathlib

root = pathlib.Path(__file__).resolve().parents[2]
skills_dir = root / ".claude" / "skills"
names = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
required = ["## Purpose", "## Inputs", "## Workflow", "## Quality checks", "## Output",
            "## Failure handling", "## Human approval points", "## Tool assumptions"]
errors = []
for md in sorted(skills_dir.glob("*/SKILL.md")):
    text = md.read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        errors.append(f"{md}: no frontmatter"); continue
    fm = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)
    if fm.get("name", "").strip() != md.parent.name:
        errors.append(f"{md}: name != directory")
    if len(fm.get("description", "").strip()) < 40:
        errors.append(f"{md}: description too short")
    for sec in required:
        if sec not in text:
            errors.append(f"{md.parent.name}: missing '{sec}'")
    for path in re.findall(r"`((?:content-engine)/[^`\s]+)`", text):
        p = path.split("<")[0].rstrip("/")
        if "*" in p or "YYYY" in p or p.endswith(("-", "_")): continue
        if not (root / p).exists():
            errors.append(f"{md.parent.name}: references missing path {path}")
    for cmd in re.findall(r"`/([a-z-]+)`", text):
        if cmd not in names and cmd not in {"content-engine"}:
            errors.append(f"{md.parent.name}: references unknown skill /{cmd}")
print(f"{len(names)} skills checked")
print("\n".join(errors) if errors else "OK")
sys.exit(1 if errors else 0)

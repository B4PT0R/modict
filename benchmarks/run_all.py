"""Run benchmark scripts sequentially in isolated subprocesses."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parent
BASELINE_PATH = ROOT / "baseline.toml"
SCRIPTS = [
    ROOT / "typechecker_cache.py",
    ROOT / "modict_core_ops.py",
    ROOT / "path_utils_ops.py",
    ROOT / "collections_utils_ops.py",
]
LINE_RE = re.compile(r"^(?P<label>.+?)\s+(?P<us>\d+\.\d+)\s+us/op\s+best-of-(?P<repeat>\d+)$")


def load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {"meta": {}, "scripts": {}}
    with BASELINE_PATH.open("rb") as f:
        data = tomllib.load(f)
    data.setdefault("meta", {})
    raw_scripts = data.setdefault("scripts", {})
    normalized_scripts: dict[str, dict[str, float]] = {}
    for script_name, values in raw_scripts.items():
        if isinstance(values, dict) and all(isinstance(v, (int, float)) for v in values.values()):
            normalized_scripts[script_name] = dict(values)
            continue
        if isinstance(values, dict):
            flattened = _flatten_script_tables(script_name, values)
            normalized_scripts.update(flattened)
    data["scripts"] = normalized_scripts
    return data


def _flatten_script_tables(prefix: str, values: dict) -> dict[str, dict[str, float]]:
    leaf_values = {k: v for k, v in values.items() if isinstance(v, (int, float))}
    nested_values = {k: v for k, v in values.items() if isinstance(v, dict)}
    result: dict[str, dict[str, float]] = {}
    if leaf_values:
        result[prefix] = leaf_values
    for key, nested in nested_values.items():
        child_prefix = f"{prefix}.{key}"
        result.update(_flatten_script_tables(child_prefix, nested))
    return result


def dump_toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_baseline(data: dict) -> None:
    lines: list[str] = []
    meta = data.get("meta", {})
    lines.append("[meta]")
    for key in sorted(meta):
        raw = meta[key]
        if isinstance(raw, str):
            lines.append(f"{key} = {dump_toml_string(raw)}")
        else:
            lines.append(f"{key} = {raw}")

    scripts = data.get("scripts", {})
    for script_name in sorted(scripts):
        lines.append("")
        lines.append(f"[scripts.{dump_toml_string(script_name)}]")
        for label in sorted(scripts[script_name]):
            lines.append(f"{dump_toml_string(label)} = {scripts[script_name][label]:.2f}")

    BASELINE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_results(stdout: str) -> dict[str, float]:
    results: dict[str, float] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = LINE_RE.match(line)
        if match is None:
            continue
        results[match.group("label")] = float(match.group("us"))
    return results


def print_comparison(script_name: str, current: dict[str, float], baseline: dict[str, float]) -> None:
    if not current:
        return
    print("comparison vs baseline", flush=True)
    for label, current_us in current.items():
        baseline_us = baseline.get(label)
        if baseline_us is None:
            print(f"  {label}: new benchmark, current {current_us:.2f} us/op", flush=True)
            continue
        delta_us = current_us - baseline_us
        delta_pct = (delta_us / baseline_us) * 100 if baseline_us else 0.0
        status = "improved" if delta_us < 0 else "regressed" if delta_us > 0 else "matched"
        print(
            f"  {label}: current {current_us:.2f} us/op vs baseline {baseline_us:.2f} us/op "
            f"({delta_us:+.2f} us, {delta_pct:+.1f}%, {status})",
            flush=True,
        )


def update_baseline_store(store: dict, script_name: str, current: dict[str, float]) -> None:
    scripts = store.setdefault("scripts", {})
    script_baseline = scripts.setdefault(script_name, {})
    for label, current_us in current.items():
        existing = script_baseline.get(label)
        if existing is None or current_us < existing:
            script_baseline[label] = current_us

    meta = store.setdefault("meta", {})
    meta["command"] = "python benchmarks/run_all.py"
    meta["updated_at_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_script(script: Path, store: dict) -> int:
    title = f"== {script.name} =="
    print(title, flush=True)
    print(flush=True)
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n", flush=True)
    if completed.stderr:
        print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
    current = parse_results(completed.stdout)
    baseline = store.get("scripts", {}).get(script.name, {})
    print_comparison(script.name, current, baseline)
    update_baseline_store(store, script.name, current)
    print(flush=True)
    return completed.returncode


def main() -> int:
    exit_code = 0
    store = load_baseline()
    for index, script in enumerate(SCRIPTS):
        if index:
            print("-" * 72, flush=True)
        exit_code = max(exit_code, run_script(script, store))
    write_baseline(store)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

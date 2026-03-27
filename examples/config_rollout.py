"""Config patching with merge, diff, diffed, and nested writes."""

import sys
from pathlib import Path as FSPath

sys.path.insert(0, str(FSPath(__file__).resolve().parents[1]))

from modict import MISSING, modict


class CanaryRollout(modict):
    # This nested model will be rebuilt from a stringly-typed wire payload.
    percent: int = modict.field(required=True)
    enabled: bool = modict.field(required=True)


class SerializedRollout(modict):
    # A typed envelope lets modict restore the intended runtime types on load.
    _config = modict.config(extra="forbid")

    debug: bool = modict.field(required=True)
    timeout_s: int = modict.field(required=True)
    retry_delays_s: list[int] = modict.field(required=True)
    canary: CanaryRollout = modict.field(required=True)


def main():
    # Start with plain nested data; no subclass is required for deep ops.
    base = modict(
        {
            "app": {"name": "billing-api", "debug": False},
            "deploy": {
                "region": "eu-west-1",
                "strategy": "blue-green",
                "canary": {"percent": 0},
            },
            "features": {"new_checkout": False, "legacy_banner": True},
            "services": {"payments": {"timeout_s": 5, "retries": 2}},
        }
    )

    # deepcopy() lets us build a candidate rollout without touching the baseline.
    candidate = base.deepcopy()
    candidate.merge(
        {
            "app": {"debug": True},
            # MISSING means "delete this key" in deep merge / diff flows.
            "features": {"new_checkout": True, "legacy_banner": MISSING},
            "services": {"payments": {"timeout_s": 10}},
        }
    )
    # set_nested() is useful for focused changes without manual intermediate indexing.
    candidate.set_nested("$.deploy.canary.percent", 25)

    # diff() gives a path-indexed view; diffed() gives a reusable minimal patch.
    diff = base.diff(candidate)
    patch = base.diffed(candidate)

    rebuilt = base.deepcopy()
    # merge(diffed(...)) is the practical "apply patch" workflow.
    rebuilt.merge(patch)

    assert rebuilt.deep_equals(candidate)
    assert candidate.get_nested("$.deploy.canary.percent") == 25
    assert not candidate.has_nested("$.features.legacy_banner")
    assert patch["features"]["legacy_banner"] is MISSING

    # Serialized payloads often arrive "stringly typed" from queues, env-driven jobs, or caches.
    serialized_rollout = """
    {
      "debug": "yes",
      "timeout_s": "10",
      "retry_delays_s": ["1", "5", "15"],
      "canary": {"percent": "25", "enabled": "true"}
    }
    """
    # loads() re-applies the model hints and coercion pipeline on the way back in.
    restored_types = SerializedRollout.loads(serialized_rollout)

    assert restored_types.debug is True
    assert restored_types.timeout_s == 10
    assert restored_types.retry_delays_s == [1, 5, 15]
    assert isinstance(restored_types.canary, CanaryRollout)
    assert restored_types.canary.enabled is True

    print("Base config")
    print(base.dumps(indent=2, sort_keys=True))
    print("\nMinimal patch")
    print(patch)
    print("\nRestored types from serialized rollout payload")
    print(
        {
            "debug": type(restored_types.debug).__name__,
            "timeout_s": type(restored_types.timeout_s).__name__,
            "retry_delays_s[0]": type(restored_types.retry_delays_s[0]).__name__,
            "canary": type(restored_types.canary).__name__,
            "canary.percent": type(restored_types.canary.percent).__name__,
        }
    )
    print("\nChanged paths")
    for path in sorted(diff, key=str):
        before, after = diff[path]
        print(f"{path}: {before!r} -> {after!r}")


if __name__ == "__main__":
    main()

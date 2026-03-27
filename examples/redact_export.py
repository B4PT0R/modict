"""Redact sensitive nested fields before export using Query, Path, and unwalk."""

import sys
from pathlib import Path as FSPath

sys.path.insert(0, str(FSPath(__file__).resolve().parents[1]))

from modict import Path, Query, modict


SENSITIVE_KEYS = {"email", "ip", "token"}


def is_sensitive(path: Path) -> bool:
    # Path predicates make it easy to express redaction rules by key shape.
    return tuple(path)[-1] in SENSITIVE_KEYS


def main():
    # A free-form modict works well as an in-memory nested document.
    batch = modict(
        {
            "tenant": "acme",
            "users": [
                {"email": "alice@example.com", "ip": "10.0.0.1", "country": "FR"},
                {"email": "bob@example.com", "ip": "10.0.0.2", "country": "DE"},
            ],
            "events": [
                {"type": "login", "status": "ok", "token": "tok_live_1"},
                {"type": "checkout", "status": "error", "token": "tok_live_2"},
            ],
        }
    )

    # deepcopy() keeps the original payload intact for audit / retry scenarios.
    export_ready = batch.deepcopy()

    # find(Query(...)) yields deep matches as (Path, value) pairs.
    for path, _ in list(export_ready.find(Query(is_sensitive))):
        # set_nested() can write back through the same Path objects.
        export_ready.set_nested(path, "<redacted>")

    # found() returns a {Path: value} mapping that can be inspected or post-processed.
    error_events = export_ready.found(Query("$.events[*].status", "error"))
    # walked()/unwalk() flatten and rebuild the nested structure through explicit paths.
    snapshot = export_ready.walked()
    restored = modict.unwalk(snapshot)

    assert export_ready.get_nested(Path(("users", 0, "email"))) == "<redacted>"
    assert export_ready.get_nested("$.events[1].token") == "<redacted>"
    assert [str(path) for path in error_events] == ["$.events[1].status"]
    assert restored.deep_equals(export_ready)

    print("Redacted export")
    print(export_ready.dumps(indent=2, sort_keys=True))
    print("\nWalked leaf count")
    print(len(snapshot))


if __name__ == "__main__":
    main()

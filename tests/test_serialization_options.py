import json
import pytest
from datetime import datetime, timezone

from modict import modict, Field


def test_model_dump_by_alias_uses_serialization_alias_then_alias():
    class User(modict):
        name: str = Field(aliases={"alias": "full_name"})
        age: int = Field(aliases={"serialization_alias": "age_out", "validation_alias": "age_in"})

    u = User({"full_name": "Alice", "age_in": 30})
    assert u.model_dump(by_alias=False) == {"name": "Alice", "age": 30}
    assert u.model_dump(by_alias=True) == {"full_name": "Alice", "age_out": 30}


def test_model_dump_exclude_none():
    class User(modict):
        name: str
        email: str | None = None

    u = User({"name": "Alice", "email": None})
    assert u.model_dump(exclude_none=True) == {"name": "Alice"}


def test_model_dump_json_uses_encoders_and_allow_inf_nan_config():
    class Event(modict):
        _config = modict.config(
            enforce_json=True,
            allow_inf_nan=False,
            json_encoders={datetime: lambda d: d.isoformat()},
        )
        ts: datetime

    e = Event({"ts": datetime(2020, 1, 1, tzinfo=timezone.utc)})
    s = e.model_dump_json()
    assert json.loads(s) == {"ts": "2020-01-01T00:00:00+00:00"}


def test_dumps_supports_by_alias_and_exclude_none():
    class User(modict):
        name: str = Field(aliases={"alias": "full_name"})
        email: str | None = None

    u = User({"full_name": "Alice"})
    data = json.loads(u.dumps(by_alias=True, exclude_none=True))
    assert data == {"full_name": "Alice"}


def test_dump_rejects_unknown_alias_when_extra_forbid():
    class User(modict):
        _config = modict.config(extra="forbid")
        name: str = Field(aliases={"alias": "full_name"})

    with pytest.raises(KeyError):
        User({"NAME": "Alice"})

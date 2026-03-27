from __future__ import annotations

import copy
from dataclasses import MISSING as DC_MISSING
from dataclasses import dataclass, field, fields
from typing import Any, FrozenSet


@dataclass(init=False)
class Config:
    """Shared config base class (explicit-field tracking + merge/copy).

    Subclasses are expected to be dataclasses with `init=False` and should
    override `_normalize_kwargs()` and `_unknown_keys_error()` as needed.
    """

    _explicit: FrozenSet[str] = field(default_factory=frozenset, init=False, repr=False)

    @classmethod
    def _normalize_kwargs(cls, kwargs: dict[str, Any]) -> dict[str, Any]:
        return kwargs

    @classmethod
    def _unknown_keys_error(cls, unknown: set[str]) -> TypeError:
        unknown_list = ", ".join(sorted(unknown))
        return TypeError(f"Unsupported config option(s): {unknown_list}.")

    @classmethod
    def _validate_known_kwargs(cls, kwargs: dict[str, Any]) -> None:
        field_names = {f.name for f in fields(cls) if f.init and f.name != "_explicit"}
        if "check_values" in kwargs and "check_values" in field_names:
            cv = kwargs["check_values"]
            if not isinstance(cv, bool):
                raise TypeError("check_values must be True or False")
        if "check_keys" in kwargs and "check_keys" in field_names:
            ck = kwargs["check_keys"]
            if not isinstance(ck, bool):
                raise TypeError("check_keys must be True or False")

    def __init__(self, **kwargs: Any):
        normalized = type(self)._normalize_kwargs(dict(kwargs))

        allowed = {f.name for f in fields(type(self)) if f.init and f.name != "_explicit"}
        unknown = set(normalized).difference(allowed)
        if unknown:
            raise type(self)._unknown_keys_error(unknown)

        type(self)._validate_known_kwargs(normalized)

        object.__setattr__(self, "_explicit", frozenset(normalized.keys()))

        for f in fields(type(self)):
            if not f.init or f.name == "_explicit":
                continue
            if f.name in normalized:
                value = normalized[f.name]
            else:
                if f.default is not DC_MISSING:
                    value = f.default
                elif f.default_factory is not DC_MISSING:  # type: ignore[attr-defined]
                    value = f.default_factory()  # type: ignore[misc]
                else:
                    raise TypeError(f"Missing required field {f.name!r}")
            object.__setattr__(self, f.name, value)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_explicit":
            object.__setattr__(self, name, value)
            return

        if name == "check_values" and not isinstance(value, bool):
            raise TypeError("check_values must be True or False")
        if name == "check_keys" and not isinstance(value, bool):
            raise TypeError("check_keys must be True or False")

        field_names = {f.name for f in fields(type(self)) if f.init}
        if name in field_names:
            explicit = set(getattr(self, "_explicit", frozenset()))
            explicit.add(name)
            object.__setattr__(self, "_explicit", frozenset(explicit))

        object.__setattr__(self, name, value)

    @classmethod
    def _from_values(cls, values: dict[str, object], explicit: FrozenSet[str]):
        self = object.__new__(cls)
        for f in fields(cls):
            if f.name == "_explicit":
                continue
            object.__setattr__(self, f.name, values[f.name])
        object.__setattr__(self, "_explicit", explicit)
        return self

    def copy(self):
        values: dict[str, object] = {}
        for f in fields(type(self)):
            if not f.init or f.name == "_explicit":
                continue
            values[f.name] = copy.deepcopy(getattr(self, f.name))
        return type(self)._from_values(values, self._explicit)

    def merge(self, other):
        merged_values: dict[str, object] = {}
        for f in fields(type(self)):
            if not f.init or f.name == "_explicit":
                continue
            name = f.name
            if name in other._explicit:
                merged_values[name] = copy.deepcopy(getattr(other, name))
            else:
                merged_values[name] = copy.deepcopy(getattr(self, name))
        merged_explicit = self._explicit | other._explicit
        return type(self)._from_values(merged_values, merged_explicit)

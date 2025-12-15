import math
import pytest

from modict import modict, Field


def test_enforce_json_disallows_nan_and_inf_when_configured():
    class M(modict):
        _config = modict.config(enforce_json=True, allow_inf_nan=False)
        x: float = Field(default=0.0)

    with pytest.raises(ValueError):
        M(x=math.nan)
    with pytest.raises(ValueError):
        M(x=math.inf)
    with pytest.raises(ValueError):
        M(x=-math.inf)


def test_enforce_json_allows_nan_and_inf_by_default():
    class M(modict):
        _config = modict.config(enforce_json=True)
        x: float = Field(default=0.0)

    M(x=math.nan)
    M(x=math.inf)

import importlib

from importlib import metadata


def test_version_fallback(monkeypatch):
    """modict.__version__ should fall back to 0.0.0 when package metadata is missing."""
    import modict

    def raise_not_found(name):
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(modict.metadata, "version", raise_not_found)
    reloaded = importlib.reload(modict)
    assert reloaded.__version__ == "0.0.0"


def test_public_api_exposes_typechecked():
    """Ensure __all__ exports the typechecked decorator (regression for missing comma)."""
    import modict

    assert "typechecked" in modict.__all__

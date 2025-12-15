from modict import modict, MISSING


def test_modict_field_factory_returns_field_instance():
    class User(modict):
        name: str = modict.field(default=MISSING)

    f = User.__fields__["name"]
    assert f.default is MISSING

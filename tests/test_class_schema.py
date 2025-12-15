from modict import modict, Field
from modict import MISSING


def test_class_schema_json_basic():
    class User(modict):
        name: str
        age: int = 25

    s = User.json_schema()
    assert s["type"] == "object"
    assert s["properties"]["name"]["type"] == "string"
    assert s["properties"]["age"]["type"] == "integer"
    assert "required" not in s


def test_class_schema_json_field_metadata_and_alias_preserved():
    class User(modict):
        age: int = Field(
            default=0,
            metadata={"description": "Age in years"},
            constraints={"ge": 0, "multiple_of": 2},
        )

    s = User.json_schema()
    assert s["properties"]["age"]["minimum"] == 0
    assert s["properties"]["age"]["multipleOf"] == 2
    assert s["properties"]["age"]["description"] == "Age in years"


def test_class_schema_json_is_standard_shape():
    class User(modict):
        name: str
        age: int = 25

    s = User.json_schema()
    assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert s["type"] == "object"
    assert s["title"] == "User"
    assert set(s["properties"].keys()) == {"name", "age"}
    assert s["properties"]["name"]["type"] == "string"
    assert s["properties"]["age"]["type"] == "integer"
    assert "required" not in s
    assert "required" not in s["properties"]["name"]


def test_class_schema_json_constraints_mapping():
    class User(modict):
        name: str = Field(
            default="ab",
            constraints={"min_length": 2, "max_length": 5, "pattern": r"^[a-z]+$"},
        )
        age: int = Field(default=2, constraints={"gt": 1, "le": 10, "multiple_of": 2})

    s = User.json_schema()
    name_schema = s["properties"]["name"]
    assert name_schema["minLength"] == 2
    assert name_schema["maxLength"] == 5
    assert name_schema["pattern"] == r"^[a-z]+$"
    assert name_schema["default"] == "ab"

    age_schema = s["properties"]["age"]
    assert age_schema["exclusiveMinimum"] == 1
    assert age_schema["maximum"] == 10
    assert age_schema["multipleOf"] == 2
    assert age_schema["default"] == 2


def test_class_schema_json_metadata_mapping():
    class User(modict):
        age: int = Field(
            default=0,
            metadata={
                "title": "Age",
                "description": "Age in years",
                "examples": [0, 42],
                "deprecated": True,
            },
        )

    s = User.json_schema()
    age_schema = s["properties"]["age"]
    assert age_schema["title"] == "Age"
    assert age_schema["description"] == "Age in years"
    assert age_schema["examples"] == [0, 42]
    assert age_schema["deprecated"] is True


def test_class_schema_json_union_and_containers():
    class User(modict):
        maybe: str | None = None
        tags: list[int] = []
        props: dict[str, int] = {}

    s = User.json_schema()
    maybe_schema = s["properties"]["maybe"]
    assert "anyOf" in maybe_schema
    assert {"type": "string"} in maybe_schema["anyOf"]
    assert {"type": "null"} in maybe_schema["anyOf"]

    tags_schema = s["properties"]["tags"]
    assert tags_schema["type"] == "array"
    assert tags_schema["items"]["type"] == "integer"

    props_schema = s["properties"]["props"]
    assert props_schema["type"] == "object"
    assert props_schema["additionalProperties"]["type"] == "integer"


def test_class_schema_json_nested_modict_uses_defs_and_ref():
    class Address(modict):
        city: str

    class User(modict):
        address: Address

    s = User.json_schema()
    assert "$defs" in s
    assert "Address" in s["$defs"]
    assert s["properties"]["address"] == {"$ref": "#/$defs/Address"}
    assert s["$defs"]["Address"]["type"] == "object"
    assert s["$defs"]["Address"]["properties"]["city"]["type"] == "string"


def test_class_schema_json_excluded_fields():
    class User(modict):
        name: str
        age: int = 25

    s = User.json_schema(excluded={"age"})
    assert set(s["properties"].keys()) == {"name"}


def test_class_schema_json_additional_properties_forbid():
    class User(modict):
        _config = modict.config(extra="forbid")
        name: str

    s = User.json_schema()
    assert s["additionalProperties"] is False


def test_class_schema_json_additional_properties_default_omitted():
    class User(modict):
        name: str

    s = User.json_schema()
    assert "additionalProperties" not in s

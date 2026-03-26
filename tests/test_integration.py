"""
Integration tests for modict.
Each test exercises the interaction between at least two submodules/features:
  - modict core  ×  typechecker (coercion + strict mode)
  - modict core  ×  validators  ×  computed
  - modict core  ×  config inheritance
  - modict core  ×  Path (navigation + mutation on nested structures)
  - modict core  ×  deep operations (merge, diff) on typed instances
  - full pipeline: Field constraints + validators + computed + Path query
"""
import pytest
from typing import List
from modict import (
    modict as md,
    Field,
    Computed,
    Path,
    MISSING,
    TypeMismatchError,
)


# ---------------------------------------------------------------------------
# Coercion pipeline × typed fields
# Strict mode disables coercion; default (lax) coerces compatible types.
# ---------------------------------------------------------------------------

def test_lax_coercion_across_nested_typed_fields():
    """Nested typed fields are coerced through the full pipeline."""
    class Address(md):
        zip_code: int

    class Person(md):
        name: str
        age: int
        address: object

    p = Person(name=42, age="28", address=Address(zip_code="75001"))
    assert p.name == "42"
    assert p.age == 28
    assert p.address.zip_code == 75001


def test_strict_mode_blocks_coercion_on_typed_field():
    """strict=True raises on type mismatch even for normally coercible values."""
    class Rigid(md):
        _config = md.config(strict=True)
        count: int

    with pytest.raises(Exception):
        Rigid(count="5")


def test_strict_and_lax_in_inheritance_chain():
    """A strict subclass can override a lax parent config."""
    class Base(md):
        value: int

    class Strict(Base):
        _config = md.config(strict=True)

    assert Base(value="3").value == 3

    with pytest.raises(Exception):
        Strict(value="3")


# ---------------------------------------------------------------------------
# Validators × Computed × typed fields
# Combined pipeline: coerce → type-check → validate → compute.
# ---------------------------------------------------------------------------

def test_validator_runs_after_coercion():
    """Field validator receives the coerced (int) value, not the raw string."""
    seen = []

    class Model(md):
        score: int

        @md.validator("score", mode="after")
        def capture(self, value):
            seen.append(value)
            return value

    Model(score="42")
    assert seen == [42]


def test_computed_depends_on_validated_field():
    """Computed field reads a field that went through coercion + validation."""
    class BoundedCounter(md):
        raw: int

        @md.validator("raw", mode="after")
        def must_be_non_negative(self, value):
            if value < 0:
                raise ValueError("negative")
            return value

        doubled: int = Computed(lambda self: self.raw * 2)

    assert BoundedCounter(raw="7").doubled == 14

    with pytest.raises(Exception):
        BoundedCounter(raw=-1)


def test_model_validator_and_computed_together():
    """model_validator enforces cross-field invariant; Computed derives from the same fields."""
    class Rectangle(md):
        width: float
        height: float
        area: float = Computed(lambda self: self.width * self.height)

        @md.model_validator(mode="after")
        def positive_dimensions(self, values):
            if values["width"] <= 0 or values["height"] <= 0:
                raise ValueError("dimensions must be positive")
            return None

    r = Rectangle(width=3.0, height=4.0)
    assert r.area == 12.0

    with pytest.raises(ValueError):
        Rectangle(width=-1.0, height=4.0)


def test_validate_assignment_default_true():
    """By default, assignment re-runs the full pipeline (coercion + validators + computed)."""
    class Model(md):
        raw: int

        @md.validator("raw")
        def normalize(self, value):
            return abs(value)

        doubled: int = Computed(lambda self: self.raw * 2)

    m = Model(raw=-5)
    assert m.raw == 5
    assert m.doubled == 10

    m.raw = -3        # pipeline re-runs: abs(-3) = 3
    assert m.raw == 3
    assert m.doubled == 6


def test_validate_assignment_false_bypasses_pipeline():
    """validate_assignment=False stores raw values on assignment without coercion or validation."""
    class Model(md):
        _config = md.config(validate_assignment=False)
        raw: int

        @md.validator("raw")
        def normalize(self, value):
            return abs(value)

    m = Model(raw=-5)
    assert m.raw == 5   # pipeline runs at init

    m.raw = -3          # bypass: validator NOT called, value stored as-is
    assert m.raw == -3


# ---------------------------------------------------------------------------
# Config inheritance × Field overrides
# ---------------------------------------------------------------------------

def test_config_propagates_through_subclass_chain():
    """Config set on a base class is inherited and selectively overridable."""
    class Base(md):
        _config = md.config(extra="forbid")
        x: int

    class Child(Base):
        y: int = 0

    class Override(Child):
        _config = md.config(extra="allow")

    # Child inherits extra="forbid"
    with pytest.raises(Exception):
        Child(x=1, y=2, z=3)

    # Override lifts the restriction
    o = Override(x=1, y=2, z=3)
    assert o.z == 3


def test_frozen_parent_prevents_mutation_in_child():
    """frozen config is inherited; the child class is also immutable."""
    class Immutable(md):
        _config = md.config(frozen=True)
        x: int

    class StillImmutable(Immutable):
        y: int = 0

    obj = StillImmutable(x=1)
    with pytest.raises(Exception):
        obj.x = 99


# ---------------------------------------------------------------------------
# Path × nested modict structures
# ---------------------------------------------------------------------------

def test_path_resolve_deep_nested():
    class Leaf(md):
        value: int

    class Branch(md):
        leaf: object

    class Root(md):
        branch: object

    tree = Root(branch=Branch(leaf=Leaf(value=42)))
    assert Path("branch.leaf.value").resolve(tree) == 42


def test_path_set_inplace_on_nested_modict():
    class Inner(md):
        x: int

    class Outer(md):
        inner: object

    o = Outer(inner=Inner(x=1))
    Path("inner.x", root=o).set_inplace(99)
    assert o.inner.x == 99


def test_path_on_list_index():
    class Model(md):
        entries: object

    m = Model(entries=[10, 20, 30])
    assert Path("entries[1]").resolve(m) == 20


# ---------------------------------------------------------------------------
# Deep operations × typed modict instances
# merge (in-place) and diff on typed instances.
# ---------------------------------------------------------------------------

def test_merge_typed_modict_in_place():
    class Config(md):
        host: str = "localhost"
        port: int = 8080
        debug: bool = False

    base = Config()
    base.merge({"host": "prod.example.com", "debug": True})

    assert base.host == "prod.example.com"
    assert base.port == 8080
    assert base.debug is True


def test_diff_detects_changed_fields():
    class Settings(md):
        timeout: int = 30
        retries: int = 3

    a = Settings()
    b = Settings(timeout=60)
    delta = a.diff(b)

    # diff returns {Path: (old_val, new_val)} for changed leaves
    assert len(delta) == 1
    changed_paths = [str(p) for p in delta]
    assert any("timeout" in p for p in changed_paths)


def test_merge_then_deep_equals():
    base = md({"db": {"host": "localhost", "port": 5432}})
    base.merge({"db": {"port": 3306, "ssl": True}})

    assert base.db.port == 3306
    assert base.db.ssl is True
    assert base.deep_equals(md({"db": {"host": "localhost", "port": 3306, "ssl": True}}))


# ---------------------------------------------------------------------------
# Factory × Computed interdependency
# ---------------------------------------------------------------------------

def test_factory_field_is_unique_per_instance():
    class Model(md):
        entries: list = md.factory(list)

    a = Model()
    b = Model()
    a.entries.append(1)
    assert b.entries == []


def test_computed_over_factory_generated_field():
    class Basket(md):
        prices: list = md.factory(list)
        total: float = Computed(lambda self: sum(self.prices))

    b = Basket()
    assert b.total == 0.0
    b.prices.append(10.5)
    b.prices.append(4.5)
    assert b.total == 15.0


# ---------------------------------------------------------------------------
# Full pipeline: typed schema + validators + computed + Path navigation
# ---------------------------------------------------------------------------

def test_full_pipeline_order_model():
    """Realistic scenario: an order with line items, total via Computed,
    invariant via model_validator, and Path-based deep read."""

    class LineItem(md):
        name: str
        qty: int
        unit_price: float
        subtotal: float = Computed(lambda self: self.qty * self.unit_price)

    class Order(md):
        customer: str
        lines: list = md.factory(list)
        total: float = Computed(lambda self: sum(i.subtotal for i in self.lines))

        @md.model_validator(mode="after")
        def non_empty(self, values):
            if not values.get("lines"):
                raise ValueError("order must have at least one item")
            return None

    order = Order(
        customer="Alice",
        lines=[
            LineItem(name="Widget", qty=2, unit_price=9.99),
            LineItem(name="Gadget", qty=1, unit_price=24.99),
        ],
    )

    assert order.total == pytest.approx(44.97)
    assert Path("lines[0].subtotal").resolve(order) == pytest.approx(19.98)
    assert Path("lines[1].name").resolve(order) == "Gadget"

    with pytest.raises(Exception):
        Order(customer="Bob")

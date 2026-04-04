"""Adapt attribute-based objects into typed dict-compatible models."""

import sys
from pathlib import Path as FSPath

sys.path.insert(0, str(FSPath(__file__).resolve().parents[1]))

from modict import MISSING, modict


class AddressRecord:
    def __init__(self, city, country):
        self.city = city
        self.country = country


class CRMContact:
    def __init__(self):
        self.customer_id = "cus_1001"
        self.email = "  VIP@example.com "
        self.is_vip = True
        self.tags = ["beta", "newsletter"]
        self.address = AddressRecord("Paris", "FR")
        self.internal_note = "only used by the CRM"


class Address(modict):
    # from_attributes=True allows building typed models from SDK / ORM style objects.
    _config = modict.config(from_attributes=True)

    city: str = modict.field(required="always")
    country: str = modict.field(required="always")


class CustomerSnapshot(modict):
    # extra="ignore" keeps the exported contract narrow even if the source object is noisy.
    _config = modict.config(from_attributes=True, extra="ignore")
    # modict.attr(...) declares class metadata without turning it into a field.
    source_system = modict.attr("crm")

    customer_id: str = modict.field(required="always")
    email: str = modict.field(required="always")
    is_vip: bool = False
    tags: list[str] = modict.factory(list)
    address: Address = modict.field(required="always")

    @modict.validator("email")
    def normalize_email(self, value):
        # Validation/cleanup still works when the source came from attributes, not a dict.
        return value.strip().lower()

    @modict.computed(cache=True, deps=["is_vip", "tags"])
    def segment(self) -> str:
        # Computed fields are useful for outbound views derived from source state.
        if self.is_vip:
            return "vip"
        if "beta" in self.tags:
            return "beta"
        return "standard"

    # Plain business methods are left alone by the field/model machinery.
    def can_receive_priority_support(self) -> bool:
        return self.is_vip or "beta" in self.tags


class EnterpriseCustomerSnapshot(CustomerSnapshot):
    account_manager: str = "unassigned"

    # Inherited business methods still behave like normal Python methods.
    def support_summary(self) -> str:
        level = "priority" if self.can_receive_priority_support() else "standard"
        return f"{level} support via {self.account_manager}"


def main():
    contact = CRMContact()
    # The constructor reads declared fields off the object and recursively types nested ones.
    snapshot = CustomerSnapshot(contact)
    enterprise_snapshot = EnterpriseCustomerSnapshot(contact)
    enterprise_snapshot.account_manager = "Camille"
    # set_attr() is the ergonomic runtime helper for per-instance metadata that should stay off-dict.
    snapshot.set_attr("sync_context", {"job_id": "sync-2026-03-27"})

    # extract() + translate() is a simple way to shape an outbound DTO without mutating the source.
    outbound = snapshot.extract("customer_id", "email", "segment").translate(
        customer_id="customerId"
    )

    # The adapted object remains dict-compatible while exposing typed nested models.
    assert isinstance(snapshot, dict)
    assert isinstance(snapshot.address, Address)
    assert snapshot.email == "vip@example.com"
    assert snapshot.segment == "vip"
    # Metadata stays out of dict
    assert snapshot.source_system == "crm"
    assert snapshot.sync_context["job_id"] == "sync-2026-03-27"
    assert "source_system" not in snapshot
    assert "sync_context" not in snapshot
    # Business methods are callable, but they do not become stored keys.
    assert snapshot.can_receive_priority_support() is True
    assert "can_receive_priority_support" not in snapshot
    # Subclasses keep inherited methods while adding new fields and methods of their own.
    assert enterprise_snapshot.support_summary() == "priority support via Camille"
    assert "support_summary" not in enterprise_snapshot
    assert "internal_note" not in snapshot
    assert outbound["customerId"] == "cus_1001"
    assert outbound["segment"] == "vip"

    print("Typed snapshot")
    print(snapshot.dumps(indent=2, sort_keys=True))
    print("\nBusiness method output")
    print(enterprise_snapshot.support_summary())
    print("\nOutbound payload with translated keys")
    print(outbound.dumps(indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

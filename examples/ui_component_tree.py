"""React-like UI component tree with methods, runtime attrs, and diffable state."""

import sys
from pathlib import Path as FSPath

sys.path.insert(0, str(FSPath(__file__).resolve().parents[1]))

from modict import modict


class HTMLRenderer:
    def render(self, component: "UIComponent") -> str:
        attrs = [f'id="{component.component_id}"']
        attrs.extend(f'{key}="{value}"' for key, value in sorted(component.props.items()))
        if component.state:
            attrs.extend(f'data-{key}="{value}"' for key, value in sorted(component.state.items()))
        start = f"<{component.tag} {' '.join(attrs)}>"
        content = component.text or ""
        content += "".join(self.render(child) for child in component.children)
        return f"{start}{content}</{component.tag}>"


class UIComponent(modict):
    # Plain class metadata can live outside the serialized payload.
    framework = modict.attr("modict-ui")

    component_id: str
    tag: str = "div"
    text: str | None = None
    props: dict[str, str] = modict.factory(dict)
    state: dict[str, bool] = modict.factory(dict)
    children: list["UIComponent"] = modict.factory(list)

    @classmethod
    def __wrap_init__(cls, init, *, renderer: HTMLRenderer, registry: dict[str, str]):
        # wrap(...) is the explicit path for business/runtime constructor context.
        def wrapped(*dict_args, **dict_kwargs):
            obj = init(*dict_args, **dict_kwargs)
            obj.set_attr("renderer", renderer)
            obj.set_attr("registry", registry)
            return obj

        return wrapped

    def mount(self, parent: "UIComponent | None" = None) -> None:
        # Runtime-only references stay out of the payload and out of dumps()/diff().
        self.set_attr("mounted", True)
        self.set_attr("parent", parent)
        self.set_attr("dom_ref", f"dom://{self.component_id}")
        for child in self.children:
            child.mount(self)

    def unmount(self) -> None:
        self.del_attr("mounted")
        self.del_attr("parent")
        self.del_attr("dom_ref")
        for child in self.children:
            child.unmount()

    def find_component(self, component_id: str) -> "UIComponent | None":
        # Business methods can traverse the tree directly without shadowing modict.find(...).
        if self.component_id == component_id:
            return self
        for child in self.children:
            match = child.find_component(component_id)
            if match is not None:
                return match
        return None

    def toggle_sidebar(self) -> None:
        # The serializable UI state still lives in the dict payload.
        current = self.state.get("open", False)
        self.set_nested("$.state.open", not current)

    def render(self) -> str:
        # The renderer itself is runtime context, injected outside the serializable payload.
        return self.renderer.render(self)


def build_screen() -> UIComponent:
    renderer = HTMLRenderer()
    registry = {"screen": "root", "sidebar": "left-pane", "content": "main-pane"}
    create = UIComponent.wrap(renderer=renderer, registry=registry)

    # Building the tree with nested UIComponent(...) calls makes the object nature explicit.
    sidebar = create(
        component_id="sidebar",
        tag="aside",
        props={"class": "sidebar"},
        state={"open": False},
        children=[
            create(
                component_id="nav-title",
                tag="h2",
                text="Navigation",
            )
        ],
    )

    content = create(
        component_id="content",
        tag="section",
        props={"class": "content"},
        children=[
            create(
                component_id="hero",
                tag="h1",
                text="Revenue Dashboard",
            )
        ],
    )

    return create(
        component_id="screen",
        tag="main",
        props={"class": "dashboard"},
        children=[sidebar, content],
    )


def main():
    screen = build_screen()

    # Methods and attrs make this a real object graph, not just a nested dict.
    screen.mount()
    sidebar = screen.find_component("sidebar")
    assert sidebar is not None
    assert screen.framework == "modict-ui"
    assert callable(screen.render)
    assert "mount" not in screen
    assert "framework" not in screen
    assert screen.has_attr("mounted") is True
    assert screen.dom_ref == "dom://screen"
    assert screen.registry["sidebar"] == "left-pane"
    assert sidebar.parent is screen

    # The UI state itself remains plain serializable data.
    before = UIComponent.loads(screen.dumps())
    sidebar.toggle_sidebar()
    after = UIComponent.loads(screen.dumps())
    diff = before.diff(after)

    assert screen.get_nested("$.children[0].state.open") is True
    assert "$.children[0].state.open" in {str(path) for path in diff}

    print("Rendered HTML")
    print(screen.render())
    print("\nSerialized payload")
    print(screen.dumps(indent=2, sort_keys=True))
    print("\nChanged paths after interaction")
    for path in sorted(diff, key=str):
        old, new = diff[path]
        print(f"{path}: {old!r} -> {new!r}")


if __name__ == "__main__":
    main()

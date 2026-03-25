# path_utils

Une petite librairie Python pour manipuler des chemins (paths) immuables/hachables à travers des données (dict/list) ou des objets, en s'appuyant sur `jsonpath_ng`.

## Concepts

- `PathNode`: un nœud (clé `int` ou `str`) + une référence vers le conteneur en mémoire à interroger.
- `Path`: une chaîne de `PathNode` avec des helpers (résolution, manipulation, conversion JSONPath).

## Exemple rapide

```python
from path_utils import Path

data = {"users": [{"name": "Ada"}]}
path = Path(["users", 0, "name"], root=data)
assert path.resolve() == "Ada"
assert str(path) == "$.users[0].name"

# Variante: on peut aussi utiliser un JSONPath
path2 = Path("$.users[0].name", root=data)
assert path2.resolve() == "Ada"
```

## Style “jsonpath”

Une fois un root fixé, on peut construire le chemin par accès “naturel”:

```python
from path_utils import Path

data = {"users": [{"name": "Ada"}], "a-b": {"c d": 1}, "keys": 123}
root = Path(root=data)

assert root.users[0].name.resolve() == "Ada"      # __getattr__ + __getitem__
assert root["a-b"]["c d"].resolve() == 1          # __getitem__ pour clés non-identifiants
assert root["keys"].resolve() == 123              # évite les collisions avec Path.keys
```

On peut aussi construire un chemin “symbolique” (sans root) puis le ré-attacher via `Path(path, root=...)` ou `set_root(...)`:

```python
from path_utils import Path

data = {"users": [{"name": "Ada"}]}

p1 = Path(("users", 0, "name"))
p2 = Path("$.users[0].name")

assert Path(p1, root=data).resolve() == "Ada"
assert Path(p2, root=data).resolve() == "Ada"

p3 = Path(("users", 0, "name"))
p3.set_root(data)
assert p3.resolve() == "Ada"
```

Pour résoudre sans re-bind, on peut fournir explicitement un conteneur de départ:

```python
from path_utils import Path

data = {"users": [{"name": "Ada"}]}
p = Path(("users", 0, "name"))
assert p.resolve(data) == "Ada"
```

Note: un premier `resolve(data)` sur un chemin symbolique met en cache les références de conteneur dans les nœuds, ce qui permet ensuite `p.resolve()` sans repasser le conteneur. Ensuite, si vous tentez de résoudre le même `Path` depuis une autre racine, une `ResolutionError` est levée (cache incohérent).

## Utilitaires

```python
from path_utils import Path

data = {"a": {"b": 1}}
assert Path(("a", "b")).exists(data) is True
assert (Path(("a",)) + "missing").exists(data) is False
```

Marche récursive sur les feuilles:

```python
data = {"a": {"b": 1}, "c": [2, {"d": 3}]}
for path, value in Path.walk(data):
    print(str(path), value)
```

Optionnellement, on peut aussi marcher dans les attributs d'objets (ex: dataclasses):

```python
for path, value in Path.walk(data, walk_objects=True):
    print(str(path), value)
```

## Requêtes JSONPath (via `jsonpath_ng`)

`find_paths()` évalue une expression JSONPath et renvoie les chemins concrets (donc manipulables) vers chaque match.

```python
from path_utils import find_paths

data = {"users": [{"name": "Ada"}, {"name": "Grace"}]}
paths = find_paths(data, "$.users[*].name")
assert [p.keys for p in paths] == [("users", 0, "name"), ("users", 1, "name")]
assert [p.resolve() for p in paths] == ["Ada", "Grace"]
```

## Notes

- Les classes sont hachables; les références de conteneur ne participent pas à l'égalité/le hash de `PathNode` (seule la clé compte).
- `Path.set_inplace()` / `Path.delete_inplace()` mutent le conteneur pointé (dict/list/attribut) quand c'est possible.

# _collections_utils - Infrastructure Package

## Vue d'Ensemble

Package d'infrastructure pour la gestion de collections, chemins et données dans Dyfract. Fournit des utilitaires robustes basés sur JSONPath (RFC 9535) pour naviguer et manipuler des structures de données imbriquées.

## Position dans l'Architecture

```
dyfract/
├── _collections_utils/    ← Package d'infrastructure (vous êtes ici)
│   ├── _path.py           ← JSONPath avec capture d'instances
│   ├── _types.py          ← Types et prédicats
│   ├── _basic.py          ← Opérations de base
│   ├── _advanced.py       ← Opérations avancées
│   ├── _view.py           ← Vues de collections
│   └── _missing.py        ← Sentinelle MISSING
├── reactive_data/         ← Utilise _collections_utils
├── backend/               ← Utilise _collections_utils
└── ...
```

## Modules

### 📍 _path.py - JSONPath Support

Classes pour manipulation de chemins avec métadonnées complètes.

**Classes principales:**
- `Path` - Chemin JSONPath avec composants typés
- `PathKey` - Composant individuel (clé + métadonnées)

**Fonctionnalités:**
- ✅ Parsing/formatting JSONPath (RFC 9535)
- ✅ Capture d'instances de conteneurs (weakref)
- ✅ Validation dynamique de chemins
- ✅ Résolution sûre avec gestion d'erreurs
- ✅ Sérialisation/désérialisation

**Exemples:**
```python
from collections_utils import Path, PathKey

# Création de chemins
path = Path.from_jsonpath("$.users[0].name")
path = Path.from_tuple(('users', 0, 'name'))

# Résolution
data = {'users': [{'name': 'Alice'}]}
value = path.resolve(data)  # 'Alice'

# Avec capture d'instances (types custom)
class MyDict(dict):
    pass

root = MyDict({'a': {'b': 1}})
path_tracked = path.with_container_types(root)
path_tracked.is_still_valid()  # True

# Manipulation
parent_path = path.parent()
child_path = path.add_key('email')
```

**Documentation détaillée:** [../backend/PATH_CONTAINER_CAPTURE.md](../backend/PATH_CONTAINER_CAPTURE.md)

### 🔍 _types.py - Types et Prédicats

Définitions de types et fonctions de vérification.

**Type Aliases:**
- `Key` - Union[int, str]
- `Container` - Union[Mapping, Sequence]
- `PathType` - Union[str, Tuple[Key, ...], Path]

**Fonctions:**
```python
from collections_utils import (
    is_container,
    is_mutable_container,
    is_dict_like,
    is_list_like,
)

is_dict_like({'a': 1})     # True
is_list_like([1, 2, 3])    # True
is_container({'a': 1})     # True (exclut str/bytes)
```

### 🔧 _basic.py - Opérations de Base

Opérations simples sur conteneurs.

**Fonctions:**
```python
from collections_utils import (
    get_key,
    set_key,
    has_key,
    keys,
    unroll,
)

# get_key, set_key, has_key - comme dict mais marche sur Mapping/Sequence
has_key(data, 'name')
value = get_key(data, 'name', default='Unknown')
set_key(data, 'name', 'Alice')

# Itération
for key in keys(data):
    print(key, get_key(data, key))
```

### ⚙️ _advanced.py - Opérations Avancées

Opérations complexes sur structures imbriquées.

**Fonctions principales:**
```python
from collections_utils import (
    get_nested,
    set_nested,
    del_nested,
    has_nested,
    walk,
    deep_merge,
    deep_equals,
    diff_nested,
)

# Accès imbriqué (chemins)
value = get_nested(data, ['users', 0, 'name'])
set_nested(data, ['users', 0, 'email'], 'alice@example.com')

# Parcours récursif
for path, value in walk(data):
    print(f"{path}: {value}")

# Fusion profonde
merged = deep_merge(dict1, dict2)

# Comparaison
are_equal = deep_equals(data1, data2)
differences = diff_nested(data1, data2)
```

### 👁️ _view.py - Vues de Collections

Vue read-only sur collections.

```python
from collections_utils import View

view = View(my_dict)
# Lecture seule, mutations propagées à l'original
```

### ⚠️ _missing.py - Sentinelle

```python
from collections_utils import MISSING

def func(arg=MISSING):
    if arg is MISSING:
        # Pas fourni
        ...
```

### 🧾 _json.py - Helpers JSON

Petits helpers pour produire des payloads JSON (sans ajouter de logique “métier”):

```python
from datetime import datetime
from collections_utils import to_jsonable, json_dumps

payload = to_jsonable(
    {"ts": datetime(2020, 1, 1), "tags": {"a", "b"}},
    encoders={datetime: lambda dt: dt.isoformat()},
)
assert payload == {"ts": "2020-01-01T00:00:00", "tags": ["a", "b"]}

text = json_dumps(payload, indent=2, sort_keys=True)
```

## Import Simplifié

Tout est accessible depuis le package principal:

```python
# Import complet
from collections_utils import (
    Path,
    PathKey,
    is_dict_like,
    is_list_like,
    get_nested,
    walk,
    deep_merge,
)

# Ou imports spécifiques
from collections_utils._path import Path
from collections_utils._advanced import walk
```

## Cas d'Usage Typiques

### 1. Navigation de Données Complexes

```python
from collections_utils import Path, get_nested

# Données API
api_response = {
    'data': {
        'users': [
            {'id': 1, 'profile': {'name': 'Alice'}},
            {'id': 2, 'profile': {'name': 'Bob'}}
        ]
    }
}

# Avec Path
path = Path.from_jsonpath("$.data.users[0].profile.name")
name = path.resolve(api_response)

# Ou avec get_nested
name = get_nested(api_response, ['data', 'users', 0, 'profile', 'name'])
```

### 2. Modification Sûre de Structures

```python
from collections_utils import set_nested, has_nested

# Vérification avant modification
if has_nested(config, ['server', 'port']):
    set_nested(config, ['server', 'port'], 8080)
```

### 3. Comparaison et Fusion

```python
from collections_utils import deep_equals, deep_merge, diff_nested

# Comparer configurations
if not deep_equals(config_prod, config_staging):
    differences = diff_nested(config_prod, config_staging)
    print("Différences:", differences)

# Fusionner avec priorité
final_config = deep_merge(default_config, user_config)
```

### 4. Validation Dynamique (Types Custom)

```python
from collections_utils import Path

class ObservableDict(dict):
    pass

data = ObservableDict({'users': ObservableDict({'alice': {'age': 30}})})

# Capture instances
path = Path.from_jsonpath("$.users.alice.age")
tracked = path.with_container_types(data)

# Validation dynamique
assert tracked.is_still_valid()  # True

del data['users']['alice']
assert not tracked.is_still_valid()  # False - détecté!
```

## Tests

```bash
python -m pytest
```

## Migration depuis reactive_data/collections_utils.py

Voir [MIGRATION_REACTIVE_DATA.md](../../MIGRATION_REACTIVE_DATA.md)

## Évolutions Futures

- [ ] Port JavaScript pour frontend (Path.js)
- [ ] Intégration avec système réactif (reactive_data)
- [ ] Support de patterns JSONPath avancés (filtres, slices)
- [ ] Cache de résolution de chemins
- [ ] Validation de schemas basée sur chemins

## Philosophie

Ce package suit les principes:
1. **Robustesse** - Gestion explicite des erreurs
2. **Typage** - Métadonnées riches pour débogage
3. **Standards** - JSONPath RFC 9535
4. **Performance** - Weak refs, pas de copies inutiles
5. **Simplicité** - API claire et documentée

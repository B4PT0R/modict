import sys
from pathlib import Path

# Allow submodule tests to import their package directly by name
# (e.g. `from collections_utils import ...`, `import typechecker`, etc.)
sys.path.insert(0, str(Path(__file__).parent))

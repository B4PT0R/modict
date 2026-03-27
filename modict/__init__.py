from importlib import metadata

from .core import modict
from .path_utils import Path
from .collections_utils import MISSING, Query
from .typechecker import (
    CoercionError,
    TypeCheckException,
    TypeCheckError,
    TypeCheckFailureError,
    TypeMismatchError,
    check_type,
    coerce,
    can_coerce,
    typechecked,
    coerced,
)

try:
    __version__ = metadata.version("modict")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0"
__title__ = "modict"
__description__ = "A hybrid dict with model-like features (typed fields, validators, computed values)."
__url__ = "https://github.com/B4PT0R/modict"
__author__ = "Baptiste FERRAND"
__email__ = "bferrand.maths@gmail.com"
__license__ = "MIT"

__all__ = [
    "modict",
    "Path",
    "MISSING",
    "Query",
    "check_type",
    "coerce",
    "can_coerce",
    "typechecked",
    "coerced",
    "TypeCheckError",
    "TypeCheckException",
    "TypeCheckFailureError",
    "TypeMismatchError",
    "CoercionError",
    "__version__",
    "__title__",
    "__description__",
    "__url__",
    "__author__",
    "__email__",
    "__license__",
]

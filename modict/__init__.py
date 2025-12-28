from importlib import metadata

from ._modict import modict
from ._modict_meta import modictConfig, Field, Factory, Computed, Validator, ModelValidator
from ._collections_utils import (
    Path,
    PathKey,
    MISSING,
)
from ._typechecker import (
    Coercer,
    CoercionError,
    TypeChecker,
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
from ._pydantic_interop import TypeCache

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
    "modictConfig",
    "Field",
    "Factory",
    "Computed",
    "Validator",
    "ModelValidator",
    "Path",
    "PathKey",
    "MISSING",
    "TypeCache",
    "check_type",
    "coerce",
    "can_coerce",
    "typechecked",
    "coerced",
    "TypeChecker",
    "TypeCheckError",
    "TypeCheckException",
    "TypeCheckFailureError",
    "TypeMismatchError",
    "Coercer",
    "CoercionError",
    "__version__",
    "__title__",
    "__description__",
    "__url__",
    "__author__",
    "__email__",
    "__license__",
]

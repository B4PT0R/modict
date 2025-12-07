from importlib import metadata

from ._modict import modict
from ._modict_meta import modictConfig, Field, Factory, Computed, Check
from ._typechecker import (
    Coercer,
    CoercionError,
    TypeCheckError,
    TypeCheckException,
    TypeCheckFailureError,
    TypeChecker,
    TypeMismatchError,
    check_type,
    coerce,
    typechecked,
)

__version__ = metadata.version("modict")
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
    "Check",
    "check_type",
    "coerce",
    "typechecked",
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

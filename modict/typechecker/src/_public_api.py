from ._typechecker import TypeChecker, TypeCheckException, TypeCheckError, TypeMismatchError, TypeCheckFailureError
from ._coercer import Coercer, CoercionError
from typing import Any, Dict, List, Set, Tuple, Union, Optional, Callable, TypeVar, get_origin, get_args
import functools
import inspect

#region: Public API

_global_coercer = None
_global_typechecker=None

def _get_global_typechecker() -> TypeChecker:
    """
    Obtient l'instance globale du typechecker (avec lazy initialization).
    Utilisé par la fonction utilitaire check_type() et le décorateur typechecked(func).
    """
    global _global_typechecker
    if _global_typechecker is None:
        _global_typechecker = TypeChecker()
    return _global_typechecker

def _get_global_coercer() -> Coercer:
    """
    Obtient l'instance globale du coercer (avec lazy initialization).
    Utilisé par la fonction utilitaire coerce().
    """
    global _global_coercer
    if _global_coercer is None:
        _global_coercer = Coercer(_get_global_typechecker())
    return _global_coercer

def reset_global_typechecker():
    """
    🔄 Reset l'instance globale du typechecker.
    Utile pour les tests ou si on veut forcer une réinitialisation.
    """
    global _global_typechecker
    _global_typechecker = None

def reset_global_coercer():
    """
    🔄 Reset l'instance globale du coercer.
    Utile pour les tests ou si on veut forcer une réinitialisation.
    """
    global _global_coercer
    _global_coercer = None

def coerce(value: Any, hint: Any) -> Any:
    """
    🚀 Fonction utilitaire simple pour coercer une valeur vers un type.
    
    Args:
        value: La valeur à coercer
        hint: Le type hint cible (int, List[str], Union[int, str], etc.)
        
    Returns:
        La valeur coercée vers le type cible
        
    Raises:
        CoercionError: Si la coercion n'est pas possible
        
    Examples:
        >>> from modict import coerce
        >>> coerce("42", int)
        42
        >>> coerce(("a", "b"), List[str])  
        ['a', 'b']
        >>> coerce("123.45", Union[int, float])
        123.45
        >>> coerce([("key", "value")], Dict[str, str])
        {'key': 'value'}
    """
    return _get_global_coercer().coerce(value, hint)

def can_coerce(value: Any, hint: Any) -> bool:
    """
    🔍 Vérifie si une valeur peut être coercée vers un type sans faire la coercion.
    
    Args:
        value: La valeur à tester
        hint: Le type hint cible
        
    Returns:
        True si la coercion est possible, False sinon
        
    Examples:
        >>> can_coerce("42", int)
        True
        >>> can_coerce("abc", int)
        False
        >>> can_coerce([1, 2, 3], List[str])
        True  # Chaque int peut être coercé en str
    """
    try:
        _get_global_coercer().coerce(value, hint)
        return True
    except CoercionError:
        return False


def check_type(hint: Any, value: Any) -> bool:
    """
    Convenience function to check if a value matches a type hint.
    
    Args:
        hint: A type annotation or typing construct
        value: The value to check against the type hint
        
    Returns:
        bool: True if the value matches the type hint
        
    Raises:
        TypeMismatchError: When the value doesn't match the type hint
        TypeCheckError: When there was an error during the type check
    """

    return _get_global_typechecker().check_type(hint, value)


# Decorator for runtime type checking
def typechecked(func):
    """
    Decorator to add runtime type checking to a function.
    
    Example:
        @typechecked
        def add(a: int, b: int) -> int:
            return a + b
    """
    if not hasattr(func, "__annotations__"):
        return func
        
    signature = inspect.signature(func)
    checker = _get_global_typechecker()
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Bind arguments to the signature
        bound_args = signature.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        # Check argument types
        for param_name, param in signature.parameters.items():
            if param_name in func.__annotations__:
                expected_type = func.__annotations__[param_name]
                arg_value = bound_args.arguments[param_name]
                
                # Special handling for *args parameter
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    # Check each item in the *args tuple
                    for item in arg_value:
                        if not checker.check_type(expected_type, item):
                            raise TypeMismatchError(
                                f"Argument '{param_name}' has invalid item: "
                                f"expected {expected_type}, got {type(item)}"
                            )
                # Special handling for **kwargs parameter
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    # Check each value in the **kwargs dict
                    for key, item in arg_value.items():
                        if not checker.check_type(expected_type, item):
                            raise TypeMismatchError(
                                f"Argument '{param_name}[{key}]' has invalid type: "
                                f"expected {expected_type}, got {type(item)}"
                            )
                # Normal parameter
                else:
                    if not checker.check_type(expected_type, arg_value):
                        raise TypeMismatchError(
                            f"Argument '{param_name}' has invalid type: "
                            f"expected {expected_type}, got {type(arg_value)}"
                        )
        
        # Call the function
        result = func(*args, **kwargs)
        
        # Check return type
        if "return" in func.__annotations__:
            return_type = func.__annotations__["return"]
            if not checker.check_type(return_type, result):
                raise TypeMismatchError(
                    f"Return value has invalid type: "
                    f"expected {return_type}, got {type(result)}"
                )
        
        return result
    
    return wrapper


def coerced(func):
    """
    Decorator to coerce args/kwargs and return values, then type-check them.
    Coercion is attempted first; type checking runs on the coerced values.
    """
    if not hasattr(func, "__annotations__"):
        return func

    signature = inspect.signature(func)
    coercer = _get_global_coercer()
    checker = _get_global_typechecker()

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = signature.bind(*args, **kwargs)
        bound_args.apply_defaults()

        for param_name, param in signature.parameters.items():
            if param_name not in func.__annotations__:
                continue

            expected_type = func.__annotations__[param_name]
            arg_value = bound_args.arguments[param_name]

            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                coerced_items = []
                for item in arg_value:
                    try:
                        coerced_items.append(coercer.coerce(item, expected_type))
                    except CoercionError:
                        coerced_items.append(item)
                bound_args.arguments[param_name] = tuple(coerced_items)
                for item in bound_args.arguments[param_name]:
                    if not checker.check_type(expected_type, item):
                        raise TypeMismatchError(
                            f"Argument '{param_name}' has invalid item: "
                            f"expected {expected_type}, got {type(item)}"
                        )
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                coerced_kwargs = {}
                for key, item in arg_value.items():
                    try:
                        coerced_kwargs[key] = coercer.coerce(item, expected_type)
                    except CoercionError:
                        coerced_kwargs[key] = item
                bound_args.arguments[param_name] = coerced_kwargs
                for key, item in bound_args.arguments[param_name].items():
                    if not checker.check_type(expected_type, item):
                        raise TypeMismatchError(
                            f"Argument '{param_name}[{key}]' has invalid type: "
                            f"expected {expected_type}, got {type(item)}"
                        )
            else:
                try:
                    bound_args.arguments[param_name] = coercer.coerce(arg_value, expected_type)
                except CoercionError:
                    pass
                if not checker.check_type(expected_type, bound_args.arguments[param_name]):
                    raise TypeMismatchError(
                        f"Argument '{param_name}' has invalid type: "
                        f"expected {expected_type}, got {type(bound_args.arguments[param_name])}"
                    )

        result = func(*bound_args.args, **bound_args.kwargs)

        if "return" in func.__annotations__:
            return_type = func.__annotations__["return"]
            try:
                result = coercer.coerce(result, return_type)
            except CoercionError:
                pass
            if not checker.check_type(return_type, result):
                raise TypeMismatchError(
                    f"Return value has invalid type: "
                    f"expected {return_type}, got {type(result)}"
                )
        return result

    return wrapper
#endregion

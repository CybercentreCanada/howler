def docstring_parameters(**kwargs: dict[str, str]):  # pragma: no cover
    """Substitute variables in docstring.

    This annotation modifies the docstring of an objects to insure that Howler's dynamic api documentation is
    always up to date.

    Args:
        substitutions (dict[str, Any]): Dictionary of substitutions
        **args (str): Individual substitutions

    Returns:
        None: This annotation directly modifies an object's docstring

    Examples:
        @docstring_parameters({cake="Black Forest", topping="Cherry"})\n
        def bake():\n
        '''Bake a cake of flavour $(cake) with topping $(topping)'''\n

        @docstring_parameters(danger="low")\n
        def assess():\n
        '''This docstring's danger level is $(danger)'''
    """

    def dec(obj):
        obj.__doc__ = obj.__doc__ % ({**kwargs})
        return obj

    return dec

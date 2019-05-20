"""
This package contains the REST API code for AnyDex
"""


def has_param(parameters, name):
    return name in parameters and len(parameters[name]) > 0


def get_param(parameters, name):
    if not has_param(parameters, name):
        return None
    return parameters[name][0]

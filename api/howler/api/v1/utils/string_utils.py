from flask import request


def parse_wait_flag():
    """Check the request args for the wait flag and return the correct es key"""
    return "wait_for" if request.args.get("wait", "").lower() == "true" else None

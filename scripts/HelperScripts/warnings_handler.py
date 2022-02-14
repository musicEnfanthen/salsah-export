import re
import warnings


def handle_warnings(msg: str):
    muted_warnings = [
        r'regex of warning you want to ignore',
    ]

    for muted_warning in muted_warnings:
        if re.search(pattern = muted_warning, string = msg):
            return
    
    warnings.warn(msg, stacklevel = 1)

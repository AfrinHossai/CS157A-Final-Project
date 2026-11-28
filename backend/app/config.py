import os
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

_dotenv = {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}


def setting(name, default=None, allow_blank=False):
    for source in (_dotenv, os.environ):
        value = source.get(name)
        if value is not None and (value != "" or allow_blank):
            return value
    if default is not None:
        return default
    raise RuntimeError(f"{name} is not set in {ENV_FILE} or the environment.")

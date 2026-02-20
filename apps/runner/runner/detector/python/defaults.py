"""Default commands for Python project types, keyed by package manager."""

INSTALL_CMDS: dict[str, str] = {
    "poetry": "poetry install",
    "uv": "uv sync",
    "pip": "pip install -r requirements.txt",
    "pipenv": "pipenv install",
}

# Default install when no lock / manifest signals are found
FALLBACK_INSTALL_CMD = "pip install -r requirements.txt"

# Default test command per framework (framework → cmd)
FRAMEWORK_TEST_CMDS: dict[str, str] = {
    "django": "python manage.py test",
}

# Generic Python test default
DEFAULT_TEST_CMD = "pytest"

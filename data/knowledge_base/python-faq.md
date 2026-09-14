# Python troubleshooting FAQ

## ModuleNotFoundError

This error means Python started, but the package is not installed in the same environment used to run the app.

Required checks:

1. Confirm the interpreter: `python -c "import sys; print(sys.executable)"`
2. Install into that same environment: `pip install requests`
3. If you use a virtual environment, activate it before installing: `source .venv/bin/activate`
4. Recheck the import: `python -c "import requests; print(requests.__version__)"`

Do not mix system Python, Homebrew Python, and a project `.venv`. TechAssist itself must be run with the project virtual environment.

## ImportError vs ModuleNotFoundError

`ModuleNotFoundError` is a missing package or wrong interpreter. `ImportError` can also mean a circular import or a local file that shadows a package name. Rename project files such as `requests.py` if they collide with library names.

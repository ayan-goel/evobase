"""Tests for the Python ecosystem detector.

All tests use in-memory fixtures written to tmp_path — no real repos cloned.
"""

from pathlib import Path

import pytest

from runner.detector.python import detect_python
from runner.detector.orchestrator import detect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _pyproject(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "pyproject.toml"
    p.write_text(content, encoding="utf-8")
    return tmp_path


def _requirements(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "requirements.txt"
    p.write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Framework detection from pyproject.toml (PEP 517 layout)
# ---------------------------------------------------------------------------

class TestPyprojectFrameworkDetection:
    def test_fastapi_from_project_deps(self, tmp_path):
        _pyproject(tmp_path, """
[project]
dependencies = ["fastapi>=0.100", "uvicorn"]
""")
        result = detect_python(tmp_path)
        assert result.framework == "fastapi"
        assert result.language == "python"

    def test_django_from_project_deps(self, tmp_path):
        _pyproject(tmp_path, """
[project]
dependencies = ["Django>=4.2"]
""")
        result = detect_python(tmp_path)
        assert result.framework == "django"

    def test_flask_from_project_deps(self, tmp_path):
        _pyproject(tmp_path, """
[project]
dependencies = ["Flask>=3.0"]
""")
        result = detect_python(tmp_path)
        assert result.framework == "flask"

    def test_starlette_from_project_deps(self, tmp_path):
        _pyproject(tmp_path, """
[project]
dependencies = ["starlette>=0.28"]
""")
        result = detect_python(tmp_path)
        assert result.framework == "starlette"

    def test_fastapi_takes_priority_over_starlette(self, tmp_path):
        _pyproject(tmp_path, """
[project]
dependencies = ["fastapi>=0.100", "starlette>=0.28"]
""")
        result = detect_python(tmp_path)
        assert result.framework == "fastapi"


class TestPoetryFrameworkDetection:
    def test_fastapi_from_poetry_deps(self, tmp_path):
        _pyproject(tmp_path, """
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.100"
uvicorn = {extras = ["standard"], version = "^0.24"}
""")
        result = detect_python(tmp_path)
        assert result.framework == "fastapi"

    def test_django_from_poetry_deps(self, tmp_path):
        _pyproject(tmp_path, """
[tool.poetry.dependencies]
python = "^3.11"
Django = "^4.2"
""")
        result = detect_python(tmp_path)
        assert result.framework == "django"


# ---------------------------------------------------------------------------
# Framework detection from requirements.txt
# ---------------------------------------------------------------------------

class TestRequirementsFrameworkDetection:
    def test_fastapi_from_requirements(self, tmp_path):
        _requirements(tmp_path, "fastapi>=0.100.0\nuvicorn\n")
        result = detect_python(tmp_path)
        assert result.framework == "fastapi"
        assert result.language == "python"

    def test_django_from_requirements(self, tmp_path):
        _requirements(tmp_path, "Django==4.2.7\npsycopg2-binary\n")
        result = detect_python(tmp_path)
        assert result.framework == "django"

    def test_flask_from_requirements(self, tmp_path):
        _requirements(tmp_path, "Flask==3.0.0\nSQLAlchemy\n")
        result = detect_python(tmp_path)
        assert result.framework == "flask"

    def test_comments_and_flags_ignored(self, tmp_path):
        _requirements(tmp_path, "# production deps\n-r base.txt\nflask>=2.0\n")
        result = detect_python(tmp_path)
        assert result.framework == "flask"

    def test_no_known_framework_returns_none(self, tmp_path):
        _requirements(tmp_path, "requests\nboto3\npydantic\n")
        result = detect_python(tmp_path)
        assert result.framework is None
        assert result.language == "python"


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------

class TestPackageManagerDetection:
    def test_poetry_from_lock_file(self, tmp_path):
        _pyproject(tmp_path, "[tool.poetry]\nname = 'myapp'\n")
        (tmp_path / "poetry.lock").write_text("# poetry lock\n")
        result = detect_python(tmp_path)
        assert result.package_manager == "poetry"
        assert result.install_cmd == "poetry install"

    def test_uv_from_lock_file(self, tmp_path):
        _requirements(tmp_path, "fastapi\n")
        (tmp_path / "uv.lock").write_text("# uv lock\n")
        result = detect_python(tmp_path)
        assert result.package_manager == "uv"
        assert result.install_cmd == "uv sync"

    def test_pipenv_from_lock_file(self, tmp_path):
        _requirements(tmp_path, "flask\n")
        (tmp_path / "Pipfile.lock").write_text("{}\n")
        result = detect_python(tmp_path)
        assert result.package_manager == "pipenv"
        assert result.install_cmd == "pipenv install --dev"

    def test_poetry_from_pyproject_section(self, tmp_path):
        _pyproject(tmp_path, "[tool.poetry]\nname = 'myapp'\n")
        result = detect_python(tmp_path)
        assert result.package_manager == "poetry"

    def test_pip_fallback_from_requirements_txt(self, tmp_path):
        _requirements(tmp_path, "flask\n")
        result = detect_python(tmp_path)
        assert result.package_manager == "pip"
        assert result.install_cmd == "pip install -r requirements.txt"

    def test_pip_includes_requirements_dev_when_present(self, tmp_path):
        _requirements(tmp_path, "flask\n")
        (tmp_path / "requirements-dev.txt").write_text("pytest\n", encoding="utf-8")
        result = detect_python(tmp_path)
        assert result.package_manager == "pip"
        assert result.install_cmd == (
            "pip install -r requirements.txt && "
            "pip install -r requirements-dev.txt"
        )

    def test_pip_includes_requirements_subdir_test_files(self, tmp_path):
        _requirements(tmp_path, "fastapi\n")
        _write(tmp_path / "requirements" / "test.txt", "pytest\n")
        _write(tmp_path / "requirements" / "dev.txt", "ruff\n")
        result = detect_python(tmp_path)
        assert result.package_manager == "pip"
        assert result.install_cmd == (
            "pip install -r requirements.txt && "
            "pip install -r requirements/test.txt && "
            "pip install -r requirements/dev.txt"
        )


# ---------------------------------------------------------------------------
# Test command defaults
# ---------------------------------------------------------------------------

class TestTestCommandDefaults:
    def test_pytest_is_default(self, tmp_path):
        _requirements(tmp_path, "flask\n")
        result = detect_python(tmp_path)
        assert result.test_cmd == "pytest"

    def test_django_gets_manage_py_test(self, tmp_path):
        _requirements(tmp_path, "Django\n")
        result = detect_python(tmp_path)
        assert result.test_cmd == "python manage.py test"

    def test_pyproject_script_overrides_default(self, tmp_path):
        _pyproject(tmp_path, """
[project]
dependencies = ["fastapi"]

[project.scripts]
test = "pytest --cov"
""")
        result = detect_python(tmp_path)
        assert "pytest" in (result.test_cmd or "")


# ---------------------------------------------------------------------------
# Language field and orchestrator routing
# ---------------------------------------------------------------------------

class TestLanguageFieldAndRouting:
    def test_language_is_python(self, tmp_path):
        _requirements(tmp_path, "fastapi\n")
        result = detect_python(tmp_path)
        assert result.language == "python"

    def test_orchestrator_routes_to_python_via_requirements(self, tmp_path):
        _requirements(tmp_path, "flask\n")
        result = detect(tmp_path)
        assert result.language == "python"
        assert result.framework == "flask"

    def test_orchestrator_routes_to_python_via_pyproject(self, tmp_path):
        _pyproject(tmp_path, """
[project]
dependencies = ["fastapi"]
""")
        result = detect(tmp_path)
        assert result.language == "python"
        assert result.framework == "fastapi"

    def test_language_in_to_dict(self, tmp_path):
        _requirements(tmp_path, "django\n")
        result = detect_python(tmp_path)
        d = result.to_dict()
        assert d["language"] == "python"

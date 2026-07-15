from __future__ import annotations

import ast
import importlib
import pkgutil
import py_compile
from pathlib import Path

EXAMPLE_PACKAGE = "pp_fx_architecture_examples"
EXAMPLE_ROOT = Path(__file__).resolve().parents[1] / EXAMPLE_PACKAGE
PROJECT_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_SOURCE_ROOTS = (
    PROJECT_ROOT / "src",
    *sorted((PROJECT_ROOT / "packages").glob("*/src")),
)


def test_every_example_module_has_valid_syntax_and_imports() -> None:
    importlib.import_module(EXAMPLE_PACKAGE)

    python_files = sorted(EXAMPLE_ROOT.rglob("*.py"))
    assert python_files, "The architecture-example package must contain Python modules."
    for python_file in python_files:
        py_compile.compile(python_file, doraise=True)

    package = importlib.import_module(EXAMPLE_PACKAGE)
    for module in pkgutil.walk_packages(
        package.__path__,
        prefix=f"{EXAMPLE_PACKAGE}.",
    ):
        importlib.import_module(module.name)


def test_examples_live_outside_production_source() -> None:
    assert all(
        not EXAMPLE_ROOT.is_relative_to(source_root)
        for source_root in PRODUCTION_SOURCE_ROOTS
    )


def test_production_source_does_not_import_examples() -> None:
    forbidden_imports: list[str] = []

    for source_root in PRODUCTION_SOURCE_ROOTS:
        for source_file in sorted(source_root.rglob("*.py")):
            tree = ast.parse(
                source_file.read_text(encoding="utf-8"),
                filename=str(source_file),
            )
            for node in ast.walk(tree):
                imported_names: tuple[str, ...] = ()
                if isinstance(node, ast.Import):
                    imported_names = tuple(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    imported_names = (node.module,)

                if any(
                    name == EXAMPLE_PACKAGE or name.startswith(f"{EXAMPLE_PACKAGE}.")
                    for name in imported_names
                ):
                    location = f"{source_file.relative_to(PROJECT_ROOT)}:{node.lineno}"
                    forbidden_imports.append(location)

    assert forbidden_imports == []

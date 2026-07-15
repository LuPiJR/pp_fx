from __future__ import annotations

import ast
from pathlib import Path

from pp_fx_architecture_examples.application.contracts.reports import (
    ExecutionCompleted,
    ReportStatus,
    RequestRejected,
)
from pp_fx_architecture_examples.composition.bootstrap import (
    compose_example_application,
    successful_request,
    unknown_target_request,
)
from pp_fx_architecture_examples.domain.results import NodeStatus

EXAMPLES_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pp_fx_architecture_examples"
)
INDEX_PATH = Path(__file__).resolve().parents[1] / "INDEX.md"
CONCRETE_CONSTRUCTORS = {
    "PandasTableWorkspace",
    "FakeCompiledPlanRepository",
    "FakeDatasetGateway",
    "FakeParameterGateway",
    "FakeDatasetNormalizer",
    "FakeScopeResolver",
    "FakeContextExpander",
    "FakeDatasetAligner",
    "InMemoryCallableRegistry",
    "RegistryBackedFakePluginExecutor",
    "CallTrace",
    "TracingCompiledPlanRepository",
    "TracingDatasetGateway",
    "TracingParameterGateway",
    "TracingDatasetNormalizer",
    "TracingScopeResolver",
    "TracingContextExpander",
    "TracingDatasetAligner",
    "TracingPluginExecutor",
    "ProcessDatasetService",
    "PythonRequestBuilder",
    "PythonProcessingFacade",
}


def test_composed_in_memory_request_crosses_expected_layers_and_ports() -> None:
    application = compose_example_application()

    with application:
        outcome = application.process(successful_request())

        assert isinstance(outcome, ExecutionCompleted)
        assert outcome.report.status is ReportStatus.SUCCESS
        assert outcome.report.results[0].artifact.status is NodeStatus.SUCCEEDED
        assert application.workspace.disposed is False
        assert application.trace.events == [
            "composition.workspace.open",
            "delivery.python_facade",
            "plan.get:plan.example",
            "dataset.load:primary",
            "parameters.load:parameters-example",
            "dataset.normalize:primary",
            "scope.resolve:primary",
            "context.expand:primary",
            "datasets.align",
            "plugin.execute:example.speed_maximum",
        ]

    assert application.workspace.disposed is True
    assert application.trace.events[-1] == "composition.workspace.dispose"


def test_composed_unknown_target_takes_short_rejection_path() -> None:
    application = compose_example_application()

    with application:
        outcome = application.process(unknown_target_request())

    assert isinstance(outcome, RequestRejected)
    assert tuple(failure.code for failure in outcome.failures) == ("UNKNOWN_TARGET",)
    assert application.trace.events == [
        "composition.workspace.open",
        "delivery.python_facade",
        "plan.get:plan.example",
        "composition.workspace.dispose",
    ]


def test_only_composition_modules_construct_concrete_example_dependencies() -> None:
    violations: list[str] = []
    observed: set[str] = set()

    for source_file in sorted(EXAMPLES_ROOT.rglob("*.py")):
        relative = source_file.relative_to(EXAMPLES_ROOT)
        tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = _called_name(node.func)
            if called not in CONCRETE_CONSTRUCTORS:
                continue
            observed.add(called)
            if relative.parts[0] != "composition":
                violations.append(f"{relative}:{node.lineno}:{called}")

    assert violations == []
    assert observed == CONCRETE_CONSTRUCTORS


def test_example_layer_import_graph_is_acyclic_and_composition_is_outermost() -> None:
    graph = _layer_import_graph()

    assert _find_cycle(graph) is None
    assert all(
        "composition" not in dependencies
        for layer, dependencies in graph.items()
        if layer != "composition"
    )


def test_example_index_maps_every_non_initializer_module() -> None:
    index = INDEX_PATH.read_text(encoding="utf-8")
    missing = tuple(
        str(source_file.relative_to(EXAMPLES_ROOT))
        for source_file in sorted(EXAMPLES_ROOT.rglob("*.py"))
        if source_file.name != "__init__.py"
        and str(source_file.relative_to(EXAMPLES_ROOT)) not in index
    )

    assert missing == ()
    assert "pp_fx_application_overview.html" in index
    assert "Recommended reading and execution order" in index


def _called_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _layer_import_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for source_file in sorted(EXAMPLES_ROOT.rglob("*.py")):
        relative = source_file.relative_to(EXAMPLES_ROOT)
        importer = relative.parts[0]
        if source_file == EXAMPLES_ROOT / "__init__.py":
            continue
        graph.setdefault(importer, set())
        module_parts = list(relative.with_suffix("").parts)
        if module_parts[-1] == "__init__":
            module_parts.pop()
        package_parts = module_parts[:-1]
        tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
        for node in ast.walk(tree):
            imported = _imported_layer(node, package_parts)
            if imported is not None and imported != importer:
                graph[importer].add(imported)
    return graph


def _imported_layer(
    node: ast.AST,
    package_parts: list[str],
) -> str | None:
    if isinstance(node, ast.Import):
        name = node.names[0].name
        prefix = "pp_fx_architecture_examples."
        return name.removeprefix(prefix).partition(".")[0] if name.startswith(prefix) else None
    if not isinstance(node, ast.ImportFrom) or node.module is None:
        return None
    if node.level == 0:
        prefix = "pp_fx_architecture_examples."
        return node.module.removeprefix(prefix).partition(".")[0] if node.module.startswith(prefix) else None
    retained = package_parts[: len(package_parts) - (node.level - 1)]
    resolved = (*retained, *node.module.split("."))
    return resolved[0] if resolved else None


def _find_cycle(graph: dict[str, set[str]]) -> tuple[str, ...] | None:
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(layer: str) -> tuple[str, ...] | None:
        if layer in visiting:
            start = visiting.index(layer)
            return (*visiting[start:], layer)
        if layer in visited:
            return None
        visiting.append(layer)
        for dependency in sorted(graph.get(layer, ())):
            cycle = visit(dependency)
            if cycle is not None:
                return cycle
        visiting.pop()
        visited.add(layer)
        return None

    for layer in sorted(graph):
        cycle = visit(layer)
        if cycle is not None:
            return cycle
    return None

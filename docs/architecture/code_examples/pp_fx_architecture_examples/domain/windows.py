"""Complete detected child windows and isolated occurrence issues."""

from __future__ import annotations

from dataclasses import dataclass

from .failures import FailureCategory, FailureDetail
from .identifiers import OccurrenceId, ScopeId
from .scopes import ResolvedScope


@dataclass(frozen=True, slots=True)
class DetectedWindow:
    """One complete detector occurrence represented as a resolved child scope."""

    occurrence: OccurrenceId
    scope: ResolvedScope

    def __post_init__(self) -> None:
        if self.scope.parent is None:
            raise ValueError("A detected window must be a child of its detector scope.")


@dataclass(frozen=True, slots=True)
class WindowOccurrenceIssue:
    """A candidate-specific failure that does not invalidate completed siblings."""

    occurrence: OccurrenceId
    parent_scope: ScopeId
    scope_ancestry: tuple[ScopeId, ...]
    failure: FailureDetail

    def __post_init__(self) -> None:
        if not self.scope_ancestry or self.scope_ancestry[-1] != self.parent_scope:
            raise ValueError("An occurrence issue must retain its parent scope ancestry.")
        if self.failure.category is not FailureCategory.NODE:
            raise ValueError("An occurrence issue requires a node-level failure.")


@dataclass(frozen=True, slots=True)
class WindowDetectionResult:
    """All complete windows plus failures for incomplete detector candidates."""

    parent_scope: ResolvedScope
    completed: tuple[DetectedWindow, ...]
    issues: tuple[WindowOccurrenceIssue, ...]

    def __post_init__(self) -> None:
        completed_ids = tuple(window.occurrence for window in self.completed)
        issue_ids = tuple(issue.occurrence for issue in self.issues)
        if len(completed_ids) != len(set(completed_ids)):
            raise ValueError("Completed window occurrence IDs must be unique.")
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("Window issue occurrence IDs must be unique.")
        if set(completed_ids) & set(issue_ids):
            raise ValueError("One occurrence cannot be both complete and incomplete.")
        if any(window.scope.parent != self.parent_scope for window in self.completed):
            raise ValueError("Every detected window must use the detector parent scope.")
        if any(
            issue.parent_scope != self.parent_scope.id
            or issue.scope_ancestry != self.parent_scope.ancestry
            for issue in self.issues
        ):
            raise ValueError("Every occurrence issue must identify the detector scope.")

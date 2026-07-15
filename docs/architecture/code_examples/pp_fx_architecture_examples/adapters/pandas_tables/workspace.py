"""Request-scoped ownership for pandas tables hidden behind opaque handles."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import uuid4

import pandas as pd

from ...application.contracts.tables import TableHandle


class WorkspaceDisposedError(RuntimeError):
    pass


class UnknownTableHandle(LookupError):
    def __init__(self, handle: TableHandle) -> None:
        self.handle = handle
        super().__init__(f"The table handle is not owned by this workspace: {handle!r}.")


class TableWorkspace(Protocol):
    """Adapter-local interface; pandas never appears in an application port."""

    @property
    def disposed(self) -> bool: ...

    def store(self, table: pd.DataFrame, *, label: str) -> TableHandle: ...

    def resolve(self, handle: TableHandle) -> pd.DataFrame: ...

    def isolate(self, handle: TableHandle) -> pd.DataFrame: ...

    def dispose(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class PandasTableWorkspace:
    """Owns canonical frames for exactly one synchronous request lifetime."""

    def __init__(self, token_factory: Callable[[], str] | None = None) -> None:
        self._token_factory = token_factory or (lambda: uuid4().hex)
        self._tables: dict[TableHandle, pd.DataFrame] = {}
        self._disposed = False

    @property
    def disposed(self) -> bool:
        return self._disposed

    def store(self, table: pd.DataFrame, *, label: str) -> TableHandle:
        self._require_open()
        if not isinstance(table, pd.DataFrame):
            raise TypeError("A pandas table workspace stores only DataFrame values.")
        if not label or label != label.strip() or any(
            character.isspace() for character in label
        ):
            raise ValueError("A table label must be non-empty and whitespace-free.")

        handle = self._new_handle(label)
        self._tables[handle] = table
        return handle

    def resolve(self, handle: TableHandle) -> pd.DataFrame:
        self._require_open()
        try:
            return self._tables[handle]
        except KeyError as error:
            raise UnknownTableHandle(handle) from error

    def isolate(self, handle: TableHandle) -> pd.DataFrame:
        return self.resolve(handle).copy(deep=True)

    def dispose(self) -> None:
        self._tables.clear()
        self._disposed = True

    def __enter__(self) -> Self:
        self._require_open()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.dispose()

    def _new_handle(self, label: str) -> TableHandle:
        while True:
            token = self._token_factory()
            if not token or any(character.isspace() for character in token):
                raise ValueError("A workspace token must be non-empty and whitespace-free.")
            handle = TableHandle(f"table:{token}/{label}")
            if handle not in self._tables:
                return handle

    def _require_open(self) -> None:
        if self._disposed:
            raise WorkspaceDisposedError("The request-scoped table workspace is disposed.")

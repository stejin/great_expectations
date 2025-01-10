from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IncludeExcludeDefinition:
    """Include or exclude directive for a class, function or method.

    Name and/or relative filepath of class, function or method definition
    to exclude or include.

    Args:
        reason: Reason for include or exclude.
        name: name of class, method or function.
        filepath: Relative to repo_root. E.g.
            great_expectations/core/expectation_suite.py
            Required if providing `name`.
    """

    reason: str
    name: Optional[str] = None
    filepath: Optional[pathlib.Path] = None

    def __post_init__(self):
        if self.name and not self.filepath:
            raise ValueError("You must provide a filepath if also providing a name.")  # noqa: TRY003
        if not self.name and not self.filepath:
            raise ValueError(  # noqa: TRY003
                "You must provide at least a filepath or filepath and name."
            )
        if self.filepath and not self.filepath.exists():
            raise FileNotFoundError(f"File {self.filepath} does not exist.")  # noqa: TRY003

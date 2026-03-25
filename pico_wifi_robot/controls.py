"""Control models for robot UI and keyboard interactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Union

Numeric = Union[int, float]
ValueTransform = Callable[[object], object]


def identity(value: object) -> object:
    return value


@dataclass
class ButtonControl:
    label: str
    target_path_template: str
    value_transform: Optional[ValueTransform] = None
    key_binding: Optional[str] = None

    def build_path(self, value: object = None) -> str:
        transformed = self._transform(value)
        return self.target_path_template.format(value=transformed)

    def _transform(self, value: object) -> object:
        if self.value_transform is None:
            return value
        return self.value_transform(value)


@dataclass
class SliderControl:
    label: str
    target_path_template: str
    value_transform: Optional[ValueTransform] = None
    key_binding: Optional[str] = None

    def build_path(self, value: Numeric) -> str:
        transformed = self._transform(value)
        return self.target_path_template.format(value=transformed)

    def _transform(self, value: object) -> object:
        if self.value_transform is None:
            return value
        return self.value_transform(value)

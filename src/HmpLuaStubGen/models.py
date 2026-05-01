from dataclasses import dataclass, field
from enum import StrEnum, auto


class Category(StrEnum):
    SHARED = auto()
    CLIENT = auto()
    SERVER = auto()


@dataclass(slots=True)
class ParamInfo:
    type: str
    is_optional: bool = False
    category: Category = Category.SHARED
    description: str = ""


@dataclass(slots=True)
class ReturnValue:
    type: str
    name: str = ""


@dataclass(slots=True)
class MethodInfo:
    category: Category = Category.SHARED
    description: str = ""
    params: dict[str, ParamInfo] = field(default_factory=dict)
    returns: list[ReturnValue] = field(default_factory=list)
    doc_link: str | None = None


@dataclass(slots=True)
class AsyncMethodInfo(MethodInfo):
    async_of: str | None = None

from app.tools.schemas import ToolHandler


class ToolHandlerCatalog:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, tool_name: str, handler: ToolHandler) -> None:
        if tool_name in self._handlers:
            raise ValueError(f"Duplicate handler: {tool_name}")
        self._handlers[tool_name] = handler

    def get(self, tool_name: str) -> ToolHandler:
        try:
            return self._handlers[tool_name]
        except KeyError as exc:
            raise KeyError(f"Unknown handler: {tool_name}") from exc

    def names(self) -> set[str]:
        return set(self._handlers)

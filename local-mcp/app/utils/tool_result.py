import json
from collections.abc import Sequence
from typing import Any

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel


def _compact_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def compact_result(value: BaseModel | Sequence[BaseModel]) -> CallToolResult:
    """
    Serialize a tool result as unindented JSON. The SDK default pretty-prints with
    an indent of 2, which costs a third or more of the characters the model reads
    for large lists.
    """
    structured: dict[str, Any]
    if isinstance(value, BaseModel):
        structured = value.model_dump(mode="json")
        text = _compact_json(structured)
    else:
        items = [item.model_dump(mode="json") for item in value]
        structured = {"result": items}
        text = _compact_json(items)
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=structured,
    )

from collections.abc import Sequence

import pydantic_core
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel


def compact_result(value: BaseModel | Sequence[BaseModel]) -> CallToolResult:
    """
    Serialize a tool result as unindented JSON. The SDK default pretty-prints with
    an indent of 2, which costs a third or more of the characters the model reads
    for large lists.
    """
    structured = pydantic_core.to_jsonable_python(value)
    return CallToolResult(
        content=[TextContent(type="text", text=pydantic_core.to_json(value).decode())],
        structured_content=structured
        if isinstance(value, BaseModel)
        else {"result": structured},
    )

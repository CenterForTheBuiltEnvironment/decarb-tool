"""Shared mixin classes for Pydantic models."""

from pydantic import BaseModel


class DotAccessMixin:
    """Mixin providing dot-notation field access for Pydantic models."""

    def get_value(self, path: str):
        """
        Resolve a (possibly dotted) field path, e.g.:
        - "field_name"
        - "nested.field_name"

        Returns None if any part of the path doesn't exist.
        """
        parts = path.split(".")
        curr = self
        for part in parts:
            if isinstance(curr, BaseModel):
                curr = getattr(curr, part, None)
            elif isinstance(curr, dict):
                curr = curr.get(part)
            else:
                curr = getattr(curr, part, None)

            if curr is None:
                return None
        return curr

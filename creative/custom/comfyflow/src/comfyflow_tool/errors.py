"""One error type; `status` is the HTTP status the API returns for it."""

from __future__ import annotations


class FlowError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class WorkflowError(FlowError):
    """Bad workflow file, unknown parameter, or a value that cannot be converted."""


class NotFound(FlowError):
    def __init__(self, message: str):
        super().__init__(message, 404)


class ComfyUnavailable(FlowError):
    def __init__(self, message: str):
        super().__init__(message, 503)

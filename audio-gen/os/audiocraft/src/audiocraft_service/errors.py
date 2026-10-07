class ServiceError(Exception):
    """Error with an HTTP-ish status code, surfaced by both the API and MCP layers."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status

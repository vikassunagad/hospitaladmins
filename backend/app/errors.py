"""Business-rule errors. main.py turns them into clean JSON responses."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__.upper()


class Unauthorized(DomainError):
    status_code = 401


class Forbidden(DomainError):
    status_code = 403


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Invalid(DomainError):
    status_code = 422

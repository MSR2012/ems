class DomainError(Exception):
    """Base class for domain rule violations."""


class InvariantViolation(DomainError):
    """A value or aggregate would enter an invalid state."""


class InvalidStateTransition(DomainError):
    """A lifecycle transition that the aggregate does not allow."""


class NotFoundError(DomainError):
    """The requested aggregate does not exist (or is not owned by the caller)."""

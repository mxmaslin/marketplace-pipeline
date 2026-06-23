class DomainError(Exception):
    """Base domain exception."""


class InvalidSegmentError(DomainError):
    pass


class CrmConfigurationError(DomainError):
    pass

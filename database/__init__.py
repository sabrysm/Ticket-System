# Database package for database adapters and connection management

from .adapter import (
    DatabaseAdapter,
    DatabaseError,
    ConnectionError,
    TicketNotFoundError,
    DuplicateTicketError
)

__all__ = [
    'DatabaseAdapter',
    'DatabaseError',
    'ConnectionError',
    'TicketNotFoundError',
    'DuplicateTicketError'
]
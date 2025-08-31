"""Custom exceptions for Mendi BLE connection handling."""


class MendiConnectionError(Exception):
    """Base exception for all Mendi connection errors."""
    pass


class DeviceNotFoundError(MendiConnectionError):
    """Raised when device is not advertising or out of range."""
    pass


class PhantomConnectionError(MendiConnectionError):
    """Raised when device thinks it's connected but host has lost connection."""
    pass


class ReconnectionFailedError(MendiConnectionError):
    """Raised when all reconnection attempts have been exhausted."""
    pass


class ConnectionTimeoutError(MendiConnectionError):
    """Raised when no data received within timeout period."""
    pass
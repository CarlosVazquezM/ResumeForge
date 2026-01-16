"""Custom exceptions for ResumeForge."""


class ResumeForgeError(Exception):
    """Base exception for ResumeForge."""
    pass


class ConfigError(ResumeForgeError):
    """Invalid or missing configuration error."""
    pass


class ValidationError(ResumeForgeError):
    """Pydantic validation failure (wrap/extend as needed)."""
    pass


class ProviderError(ResumeForgeError):
    """Provider/network/SDK failure."""
    pass


class OrchestrationError(ResumeForgeError):
    """Pipeline orchestration failure."""
    pass

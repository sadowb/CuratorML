"""Typed exception hierarchy for the translation pipeline.

Each error maps to a specific failure mode in the translation flow,
enabling deterministic error handling in the dispatcher and actionable
metrics in ``PipelineRun.metrics_json``.
"""

from __future__ import annotations


class TranslationError(Exception):
    """Base class for all translation-stage errors."""


# ── Submit-time errors (surface as HTTP 4xx) ─────────────────────────

class TranslationConfigError(TranslationError):
    """Translation provider config is invalid or incomplete."""


class TranslationDuplicateRunError(TranslationError):
    """An active translate run for the same page+language already exists."""


class TranslationLanguageResolutionError(TranslationError):
    """Could not resolve an effective target language from request or project."""


# ── Handler-time errors (surface as job failure) ─────────────────────

class TranslationNoTextLinesError(TranslationError):
    """No eligible text regions/lines to translate on this page."""


class TranslationProviderTimeoutError(TranslationError):
    """The LLM provider timed out."""


class TranslationProviderNetworkError(TranslationError):
    """Network-level failure reaching the LLM provider."""


class TranslationInvalidJSONError(TranslationError):
    """LLM returned non-JSON or unparseable JSON after repair attempt."""


class TranslationSchemaMismatchError(TranslationError):
    """LLM JSON parsed but does not conform to LLMTranslationResponse."""


class TranslationOrderMappingError(TranslationError):
    """Translated order numbers could not be mapped to region IDs."""


class TranslationPersistenceError(TranslationError):
    """Database write failed during translation result persistence."""

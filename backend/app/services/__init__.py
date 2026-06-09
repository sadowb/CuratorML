"""Service package namespace.

Keep this module side-effect free so lightweight subpackages such as
``app.services.ml`` can be imported by the host inference process without
loading database-backed service modules.
"""

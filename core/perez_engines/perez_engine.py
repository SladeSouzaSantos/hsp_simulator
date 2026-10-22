"""Compatibility alias. Legacy wrong monthly formula is intentionally disabled."""
from .perez_engine_pvlib import PerezEnginePVLib

class PerezEngine(PerezEnginePVLib):
    pass

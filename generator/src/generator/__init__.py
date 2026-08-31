"""Synthetic document generator.

Produces parameterised NDAs as PDFs (clean or degraded "scanned"), each with a
ground-truth JSON sidecar. No network calls: text is templated, not model-written,
so output is deterministic for a given seed.
"""

__version__ = "0.1.0"

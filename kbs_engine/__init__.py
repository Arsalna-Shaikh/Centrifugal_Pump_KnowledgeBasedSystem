"""KR-2 layered inference engine for the structured pump knowledge base (knowledge_base/).

Independent of the legacy engine in src/inference_engine.py, which is left unchanged.
"""
from .engine import Case, InferenceEngine, diagnose
from .explain import explain
from .knowledge import KnowledgeBase

__all__ = ["Case", "InferenceEngine", "KnowledgeBase", "diagnose", "explain"]

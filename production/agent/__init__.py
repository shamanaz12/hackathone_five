"""
TaskFlow AI Support Agent — Agent Core
Production package for the CRM Digital FTE Factory Final Hackathon 5.
"""

# Lazy imports — only import what's actually available
def __getattr__(name):
    import importlib
    _module_map = {
        "MessageNormalizer": ".normalizer",
        "TicketClassifier": ".classifier",
        "SentimentAnalyzer": ".sentiment",
        "ResponseGenerator": ".response_generator",
        "EscalationDecider": ".escalation",
        "ConversationMemory": ".memory",
        "TaskFlowAgentPipeline": ".pipeline",
    }
    if name in _module_map:
        mod = importlib.import_module(_module_map[name], __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "MessageNormalizer",
    "TicketClassifier",
    "SentimentAnalyzer",
    "ResponseGenerator",
    "EscalationDecider",
    "ConversationMemory",
    "TaskFlowAgentPipeline",
]

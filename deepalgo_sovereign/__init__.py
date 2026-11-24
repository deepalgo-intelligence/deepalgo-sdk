from .client import DeepAlgoClient, ExecutionResult
from .emsx import SovereignEMSXHook, RegimeDecision

SovereignClient = DeepAlgoClient  # alias — both names work

__version__ = "0.2.4"
__all__ = ["DeepAlgoClient", "SovereignClient", "ExecutionResult",
           "SovereignEMSXHook", "RegimeDecision"]
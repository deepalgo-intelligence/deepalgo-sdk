from .client import DeepAlgoClient

SovereignClient = DeepAlgoClient  # alias — both names work

__version__ = "0.2.1"
__all__ = ["DeepAlgoClient", "SovereignClient"]
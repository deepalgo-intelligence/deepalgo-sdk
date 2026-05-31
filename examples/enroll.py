"""
Self-registration — get a free API key emailed to you instantly.
No account creation, no credit card required.
"""
from deepalgo_sovereign import DeepAlgoClient

DeepAlgoClient.enroll("you@email.com")
# Check your inbox — key arrives within seconds.
# Then:
# client = DeepAlgoClient(api_key="your_key_here")

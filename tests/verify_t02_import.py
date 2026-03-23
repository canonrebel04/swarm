import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

try:
    from messaging.spacetime_client import SpacetimeClient
    print("SpacetimeClient imported successfully")
    
    client = SpacetimeClient()
    print("SpacetimeClient initialized successfully")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Initialization failed: {e}")
    sys.exit(1)

print("Verification passed")

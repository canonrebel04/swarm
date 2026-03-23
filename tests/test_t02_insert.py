import asyncio
import sys
import os
import logging

# Add src to path
sys.path.append(os.path.abspath("src"))

from messaging.spacetime_client import SpacetimeClient

logging.basicConfig(level=logging.DEBUG)

async def test_insert():
    client = SpacetimeClient()
    print("Connecting...")
    await client.connect("localhost:3000", "c200719ff57f6247ab9a2a954b38ff5e456e204ecf09dd114b4734b76d33c29d")
    
    print("Inserting event...")
    # event_id, sender, payload, timestamp
    await client.insert_event(1, "test_agent", "hello spacetime", 1711080000)
    
    print("Wait for event...")
    await asyncio.sleep(2)
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_insert())

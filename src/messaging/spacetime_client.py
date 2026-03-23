import asyncio
import logging
from typing import List, Optional, Callable, Any
import os

from spacetimedb_sdk.spacetimedb_async_client import SpacetimeDBAsyncClient
from . import module_bindings

logger = logging.getLogger(__name__)

class SpacetimeClient:
    """
    Wrapper for SpacetimeDBAsyncClient to manage SDK lifecycle and connection.
    """

    def __init__(self, identity_file: str = ".swarm/spacetime_identity"):
        self.client = SpacetimeDBAsyncClient(module_bindings)
        self.identity = None
        self._is_connected = False
        self._on_connect_callbacks = []
        self._identity_file = identity_file

    def _save_auth_token(self, auth_token: str):
        """Save the auth token to a file."""
        os.makedirs(os.path.dirname(self._identity_file), exist_ok=True)
        with open(self._identity_file, "w") as f:
            f.write(auth_token)
        logger.debug(f"Saved SpacetimeDB auth token to {self._identity_file}")

    def _load_auth_token(self) -> Optional[str]:
        """Load the auth token from a file."""
        if os.path.exists(self._identity_file):
            with open(self._identity_file, "r") as f:
                return f.read().strip()
        return None

    async def connect(self, host: str, db_name: str, auth_token: Optional[str] = None, ssl_enabled: bool = False):
        """
        Connect to the SpacetimeDB module.
        """
        if auth_token is None:
            auth_token = self._load_auth_token()
            
        logger.info(f"Connecting to SpacetimeDB at {host}, database: {db_name}")
        
        def handle_connect(auth_token, identity):
            self.identity = identity
            self._is_connected = True
            self._save_auth_token(auth_token)
            logger.info(f"Connected to SpacetimeDB with identity: {identity}")
            for callback in self._on_connect_callbacks:
                callback(auth_token, identity)

        try:
            # We use a task for the run loop so it doesn't block this call
            # but wait for the connection event.
            self._run_task = asyncio.create_task(
                self.client.run(
                    auth_token,
                    host,
                    db_name,
                    ssl_enabled,
                    on_connect=handle_connect
                )
            )
            
            # Wait for connection to be established
            timeout = 10
            start_time = asyncio.get_event_loop().time()
            while not self._is_connected:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise ConnectionError(f"Connection to SpacetimeDB timed out after {timeout}s")
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Failed to connect to SpacetimeDB: {e}")
            raise

    def subscribe(self, queries: List[str]):
        """
        Subscribe to SQL queries.
        """
        if not self._is_connected:
            raise RuntimeError("Client not connected")
        
        logger.info(f"Subscribing to queries: {queries}")
        self.client.subscribe(queries)

    async def insert_event(self, event_id: int, sender: str, payload: str, timestamp: int):
        """
        Wrapper for the insert_event reducer.
        """
        if not self._is_connected:
            raise RuntimeError("Client not connected")
            
        logger.debug(f"Calling insert_event reducer: {event_id}, {sender}")
        # The SDK expects the reducer name and args as they appear in the Rust module
        # The auto-generated binding would usually handle the type packing.
        # Here we manually pack the struct-like argument.
        event_struct = {
            "event_id": event_id,
            "sender": sender,
            "payload": payload,
            "timestamp": timestamp
        }
        await self.client.call_reducer("insert_event", event_struct)

    async def close(self):
        """
        Close the connection.
        """
        if self._is_connected:
            await self.client.close()
            self._is_connected = False
            if hasattr(self, "_run_task"):
                self._run_task.cancel()
                try:
                    await self._run_task
                except asyncio.CancelledError:
                    pass
            logger.info("SpacetimeDB connection closed")

    def register_on_event(self, callback: Callable[[Any], None]):
        """
        Register a callback for transaction events.
        """
        self.client.register_on_event(callback)

    def register_on_subscription_applied(self, callback: Callable[[], None]):
        """
        Register a callback for when subscription data is applied.
        """
        self.client.register_on_subscription_applied(callback)

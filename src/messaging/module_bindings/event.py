from typing import List, Dict, Any

class Event:
    is_table_class = True
    table_name = "Event"
    primary_key = "event_id"

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.event_id = data.get("event_id")
        self.sender = data.get("sender")
        self.payload = data.get("payload")
        self.timestamp = data.get("timestamp")

    @classmethod
    def decode(cls, data: Dict[str, Any]):
        return cls(data)

from typing import List, Dict, Any

class Agent:
    is_table_class = True
    table_name = "Agent"
    primary_key = "identity"

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.identity = data.get("identity")
        self.name = data.get("name")
        self.status = data.get("status")

    @classmethod
    def decode(cls, data: Dict[str, Any]):
        return cls(data)

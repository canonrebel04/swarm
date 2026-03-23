from typing import List, Dict, Any

class Task:
    is_table_class = True
    table_name = "Task"
    primary_key = "task_id"

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.task_id = data.get("task_id")
        self.description = data.get("description")
        self.status = data.get("status")
        self.depends_on = data.get("depends_on", [])

    @classmethod
    def decode(cls, data: Dict[str, Any]):
        return cls(data)

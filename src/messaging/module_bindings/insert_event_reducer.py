import json

reducer_name = "insert_event"

def _decode_args(args):
    return json.loads(args)

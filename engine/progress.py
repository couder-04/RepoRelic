import sys
import json

def emit(stage: int, name: str, status: str, message: str):
    msg = {
        "type": "progress",
        "stage": stage,
        "name": name,
        "status": status,
        "message": message
    }
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

def emit_complete(report_path: str):
    msg = {
        "type": "complete",
        "report_path": report_path
    }
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

def request_permission(action: str, message: str) -> bool:
    msg = {
        "type": "permission",
        "action": action,
        "message": message
    }
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()
    
    # Block on stdin
    response_line = sys.stdin.readline()
    if not response_line:
        return False
    try:
        data = json.loads(response_line)
        return data.get("approved", False)
    except Exception:
        return False

def emit_error(message: str):
    msg = {
        "type": "error",
        "message": message
    }
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

import json
import os
import time

_LOG_PATH = os.path.join(os.path.expanduser("~"), "debug-6471a8.log")
_SESSION = "6471a8"


def agent_log(location, message, data=None, hypothesis_id=None, run_id="pre-fix"):
    # #region agent log
    try:
        entry = {
            "sessionId": _SESSION,
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "runId": run_id,
        }
        if hypothesis_id:
            entry["hypothesisId"] = hypothesis_id
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    # #endregion

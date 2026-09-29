"""SkillSprint AI Flask backend entry point.

The React frontend lives in /frontend and calls this API over HTTP.
"""
from backend.api import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

import sys
import os

# Ensure user site-packages is on the path
user_site = r"C:\Users\manabu\AppData\Roaming\Python\Python312\site-packages"
if user_site not in sys.path:
    sys.path.insert(0, user_site)

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    reload_enabled = os.environ.get("UVICORN_RELOAD", "false").lower() == "true"
    uvicorn.run("app.main:app", reload=reload_enabled, host="0.0.0.0", port=port)

from app import create_app
from app.db import setting

app = create_app()

if __name__ == "__main__":
    app.run(host=setting("HOST", "127.0.0.1"), port=int(setting("PORT", "5000")))

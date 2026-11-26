from flask import Flask
import auth
import db

app = Flask(__name__)
db.init_app(app)
auth.init_app(app)

@app.route('/')
def root():
    return "Hello from Flask!"

if __name__ == "__main__":
    app.run(host=db.setting("HOST", "127.0.0.1"), port=int(db.setting("PORT", "5000")))

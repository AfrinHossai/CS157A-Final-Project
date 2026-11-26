from flask import Flask
import db

app = Flask(__name__)
db.init_app(app)

@app.route('/')
def root():
    return "Hello from Flask!"

if __name__ == "__main__":
    app.run()

import os
import threading

from flask import Flask, jsonify, render_template

from detector import monitor_forever, public_status


app = Flask(__name__)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify(public_status())


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    monitor = threading.Thread(target=monitor_forever, daemon=True)
    monitor.start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))

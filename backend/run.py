"""Development entry point for the Flask-SocketIO server."""

from app.factory import create_app
from app.realtime import socketio


application = create_app()


if __name__ == "__main__":
    socketio.run(
        application,
        host="127.0.0.1",
        port=5000,
        debug=True,
        allow_unsafe_werkzeug=True,
    )

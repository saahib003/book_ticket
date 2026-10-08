from app.factory import create_app
from app.realtime import socketio


def test_client_can_join_show_room():
    app = create_app("testing")
    client = socketio.test_client(app)

    assert client.is_connected()
    client.emit("join_show", 1)
    assert {
        "name": "show_joined",
        "args": [{"show_id": 1}],
        "namespace": "/",
    } in client.get_received()
    client.disconnect()

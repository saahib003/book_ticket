"""Socket.IO rooms and seat-change notifications."""

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room

socketio = SocketIO()


@socketio.on("join_show")
def join_show(show_id: int):
    room = f"show:{int(show_id)}"
    join_room(room)
    emit("show_joined", {"show_id": int(show_id)})


@socketio.on("leave_show")
def leave_show(show_id: int):
    leave_room(f"show:{int(show_id)}")


def publish_seat_status(show_id: int, seat_ids: list[int], status: str, seat_map_version: int) -> None:
    socketio.emit("SEAT_STATUS_CHANGED", {"type": "SEAT_STATUS_CHANGED", "show_id": show_id, "seat_ids": seat_ids, "status": status, "seat_map_version": seat_map_version}, room=f"show:{show_id}")


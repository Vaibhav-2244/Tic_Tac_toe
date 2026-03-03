from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import random
import string
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

rooms = {}

@app.route('/')
def index():
    return render_template("game.html")


def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


@socketio.on("create_room")
def create_room(data):
    username = data["username"]

    room_code = generate_room_code()
    while room_code in rooms:
        room_code = generate_room_code()

    rooms[room_code] = {
        "players": [username],
        "player_info": {"X": username},
        "board": [""] * 9,
        "turn": "X",
        "scores": {"X": 0, "O": 0},
        "symbols": {request.sid: "X"}
    }

    join_room(room_code)

    emit("room_created", {
        "room": room_code,
        "symbol": "X"
    })


@socketio.on("join_room")
def join_existing_room(data):
    username = data["username"]
    room_code = data["room"]

    if room_code not in rooms:
        emit("error_message", "Room does not exist")
        return

    room = rooms[room_code]

    if len(room["players"]) >= 2:
        emit("error_message", "Room is full")
        return

    room["players"].append(username)
    room["player_info"]["O"] = username
    room["symbols"][request.sid] = "O"

    join_room(room_code)

    emit("joined_room", {
        "room": room_code,
        "symbol": "O"
    })

    emit("start_game", room=room_code)

    # 🔥 Immediately send full game state
    emit("update_board", {
        "board": room["board"],
        "turn": room["turn"],
        "winner": None,
        "draw": False,
        "scores": room["scores"],
        "players": room["player_info"]
    }, room=room_code)


@socketio.on("make_move")
def make_move(data):
    room_code = data["room"]
    index = data["index"]

    room = rooms.get(room_code)
    if not room:
        return

    symbol = room["symbols"].get(request.sid)

    # 🔥 Block if game already won
    if check_winner(room["board"]):
        return

    if 0 <= index < 9 and room["board"][index] == "" and room["turn"] == symbol:
        room["board"][index] = symbol

        winner = check_winner(room["board"])
        draw = "" not in room["board"] and not winner

        if winner:
            room["scores"][winner] += 1
        else:
            room["turn"] = "O" if symbol == "X" else "X"

        emit("update_board", {
            "board": room["board"],
            "turn": room["turn"],
            "winner": winner,
            "draw": draw,
            "scores": room["scores"],
            "players": room["player_info"]
        }, room=room_code)


@socketio.on("restart_game")
def restart_game(data):
    room_code = data["room"]
    room = rooms.get(room_code)

    if room:
        room["board"] = [""] * 9
        room["turn"] = "X"

        emit("update_board", {
            "board": room["board"],
            "turn": room["turn"],
            "winner": None,
            "draw": False,
            "scores": room["scores"],
            "players": room["player_info"]
        }, room=room_code)


def check_winner(board):
    wins = [
        [0,1,2],[3,4,5],[6,7,8],
        [0,3,6],[1,4,7],[2,5,8],
        [0,4,8],[2,4,6]
    ]
    for combo in wins:
        if board[combo[0]] != "" and \
           board[combo[0]] == board[combo[1]] == board[combo[2]]:
            return board[combo[0]]
    return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
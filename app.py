from flask import Flask, render_template, request, redirect, session, send_file
from datetime import datetime
import csv, io, json, os

app = Flask(__name__)
app.secret_key = "super-secret-key"

DATA_FILE = "data.json"

# ---------------- ADMIN CONFIG ----------------
ADMIN_PASSWORD = "kira"

# ---------------- DEFAULT STATE ----------------
state = {
    "EVENT_ACTIVE": False,
    "EVENT_NAME": "",
    "MAX_CAPACITY": 0,
    "MEMBER_PASSWORD": "",
    "TOTAL_COUNT": 0,
    "LOGS": []
}

# ---------------- LOAD / SAVE ----------------
def load_data():
    global state
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            state = json.load(f)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(state, f)

load_data()

# ---------------- MEMBER SIDE ----------------
@app.route("/")
def home():
    if not state["EVENT_ACTIVE"]:
        return render_template("no_event.html")
    return render_template("member_login.html")

@app.route("/member-auth", methods=["POST"])
def member_auth():
    if request.form.get("password") == state["MEMBER_PASSWORD"]:
        session["member_auth"] = True
        return redirect("/member-name")
    return render_template("member_login.html", error="Wrong password")

@app.route("/member-name")
def member_name():
    if not session.get("member_auth"):
        return redirect("/")
    return render_template("member_name.html", event=state["EVENT_NAME"])

@app.route("/entry", methods=["POST"])
def entry():
    if not session.get("member_auth"):
        return redirect("/")

    name = request.form.get("name")
    label = request.form.get("label")
    members = int(request.form.get("members"))

    if state["TOTAL_COUNT"] + members > state["MAX_CAPACITY"]:
        return render_template(
            "blocked.html",
            event=state["EVENT_NAME"],
            max=state["MAX_CAPACITY"]
        )

    state["TOTAL_COUNT"] += members

    state["LOGS"].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "name": name,
        "type": label,
        "members": members,
        "total": state["TOTAL_COUNT"]
    })

    save_data()
    session.pop("member_auth", None)
    return render_template("success.html")

# ---------------- ADMIN LOGIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/dashboard")
        return render_template("login.html", error="Wrong password")
    return render_template("login.html")

# ---------------- SETTINGS (NO RESET) ----------------
@app.route("/setup", methods=["GET", "POST"])
def setup():
    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        state["EVENT_NAME"] = request.form.get("event")
        state["MAX_CAPACITY"] = int(request.form.get("capacity"))
        state["MEMBER_PASSWORD"] = request.form.get("member_password")
        state["EVENT_ACTIVE"] = True
        save_data()
        return redirect("/dashboard")

    return render_template(
        "setup.html",
        event=state["EVENT_NAME"],
        capacity=state["MAX_CAPACITY"],
        member_password=state["MEMBER_PASSWORD"]
    )

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    return render_template(
        "admin.html",
        event=state["EVENT_NAME"],
        total=state["TOTAL_COUNT"],
        max=state["MAX_CAPACITY"],
        logs=state["LOGS"],
        member_password=state["MEMBER_PASSWORD"]
    )

# ---------------- RESET (MANUAL ONLY) ----------------
@app.route("/reset", methods=["POST"])
def reset():
    if not session.get("admin"):
        return redirect("/admin")

    state.update({
        "EVENT_ACTIVE": False,
        "EVENT_NAME": "",
        "MAX_CAPACITY": 0,
        "MEMBER_PASSWORD": "",
        "TOTAL_COUNT": 0,
        "LOGS": []
    })

    save_data()
    return redirect("/setup")

# ---------------- EXPORT CSV ----------------
@app.route("/export")
def export():
    if not session.get("admin"):
        return redirect("/admin")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Name", "Entry Type", "Members", "Total"])

    for l in state["LOGS"]:
        writer.writerow([
            l["time"], l["name"], l["type"], l["members"], l["total"]
        ])

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="event_entries.csv"
    )

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/admin")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)

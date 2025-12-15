from flask import Flask, render_template, request, redirect, session, send_file
from datetime import datetime
import csv, io

app = Flask(__name__)
app.secret_key = "super-secret-key"

# ---------------- ADMIN CONFIG ----------------
ADMIN_PASSWORD = "kira"

# ---------------- EVENT STATE ----------------
EVENT_ACTIVE = False
EVENT_NAME = ""
MAX_CAPACITY = 0
MEMBER_PASSWORD = ""

TOTAL_COUNT = 0
LOGS = []

# ---------------- MEMBER SIDE ----------------
@app.route("/")
def home():
    if not EVENT_ACTIVE:
        return render_template("no_event.html")
    return render_template("member_login.html")

@app.route("/member-auth", methods=["POST"])
def member_auth():
    password = request.form.get("password")
    if password == MEMBER_PASSWORD:
        session["member_auth"] = True
        return redirect("/member-name")
    return render_template("member_login.html", error="Wrong password")

@app.route("/member-name")
def member_name():
    if not session.get("member_auth"):
        return redirect("/")
    return render_template("member_name.html", event=EVENT_NAME)

@app.route("/entry", methods=["POST"])
def entry():
    global TOTAL_COUNT

    if not session.get("member_auth"):
        return redirect("/")

    name = request.form.get("name")
    label = request.form.get("label")
    members = int(request.form.get("members"))  # ✅ FIXED COUNT

    # Capacity check
    if TOTAL_COUNT + members > MAX_CAPACITY:
        return render_template("blocked.html", event=EVENT_NAME, max=MAX_CAPACITY)

    TOTAL_COUNT += members

    LOGS.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "name": name,
        "type": label,
        "members": members,
        "total": TOTAL_COUNT
    })

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
    global EVENT_ACTIVE, EVENT_NAME, MAX_CAPACITY, MEMBER_PASSWORD

    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        EVENT_NAME = request.form.get("event")
        MAX_CAPACITY = int(request.form.get("capacity"))
        MEMBER_PASSWORD = request.form.get("member_password")
        EVENT_ACTIVE = True
        return redirect("/dashboard")

    return render_template(
        "setup.html",
        event=EVENT_NAME,
        capacity=MAX_CAPACITY,
        member_password=MEMBER_PASSWORD
    )

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    return render_template(
        "admin.html",
        event=EVENT_NAME,
        total=TOTAL_COUNT,
        max=MAX_CAPACITY,
        logs=LOGS,
        member_password=MEMBER_PASSWORD
    )

# ---------------- FULL RESET ----------------
@app.route("/reset", methods=["POST"])
def reset():
    global EVENT_ACTIVE, EVENT_NAME, MAX_CAPACITY, MEMBER_PASSWORD, TOTAL_COUNT, LOGS

    EVENT_ACTIVE = False
    EVENT_NAME = ""
    MAX_CAPACITY = 0
    MEMBER_PASSWORD = ""
    TOTAL_COUNT = 0
    LOGS = []

    return redirect("/setup")

# ---------------- EXPORT CSV ----------------
@app.route("/export")
def export():
    if not session.get("admin"):
        return redirect("/admin")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Name", "Entry Type", "Members", "Total"])

    for l in LOGS:
        writer.writerow([l["time"], l["name"], l["type"], l["members"], l["total"]])

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

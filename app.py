from flask import Flask, render_template, request, redirect, session, send_file
from datetime import datetime
import psycopg2, os, csv, io

app = Flask(__name__)
app.secret_key = "super-secret-key"

ADMIN_PASSWORD = "kira"
DATABASE_URL = os.environ.get("DATABASE_URL")

# ---------------- DB CONNECTION ----------------
def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS event (
                    id SERIAL PRIMARY KEY,
                    active BOOLEAN,
                    name TEXT,
                    capacity INTEGER,
                    member_password TEXT,
                    total INTEGER
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id SERIAL PRIMARY KEY,
                    time TEXT,
                    name TEXT,
                    type TEXT,
                    members INTEGER,
                    total INTEGER
                );
            """)
            cur.execute("SELECT COUNT(*) FROM event;")
            if cur.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO event (active, name, capacity, member_password, total)
                    VALUES (FALSE, '', 0, '', 0);
                """)
        conn.commit()

init_db()

# ---------------- HELPERS ----------------
def get_event():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT active, name, capacity, member_password, total FROM event LIMIT 1;")
            return cur.fetchone()

def update_event(**kwargs):
    fields = ", ".join(f"{k}=%s" for k in kwargs)
    values = list(kwargs.values())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE event SET {fields};", values)
        conn.commit()

# ---------------- MEMBER ----------------
@app.route("/")
def home():
    active, name, capacity, member_password, total = get_event()
    if not active:
        return render_template("no_event.html")
    return render_template("member_login.html")

@app.route("/member-auth", methods=["POST"])
def member_auth():
    password = request.form.get("password")
    active, name, capacity, member_password, total = get_event()
    if password == member_password:
        session["member_auth"] = True
        return redirect("/member-name")
    return render_template("member_login.html", error="Wrong password")

@app.route("/member-name")
def member_name():
    if not session.get("member_auth"):
        return redirect("/")
    _, name, _, _, _ = get_event()
    return render_template("member_name.html", event=name)

@app.route("/entry", methods=["POST"])
def entry():
    if not session.get("member_auth"):
        return redirect("/")

    name = request.form.get("name")
    label = request.form.get("label")
    members = int(request.form.get("members"))

    active, event_name, capacity, mp, total = get_event()

    if total + members > capacity:
        return render_template("blocked.html", event=event_name, max=capacity)

    new_total = total + members

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO logs (time, name, type, members, total) VALUES (%s,%s,%s,%s,%s);",
                (datetime.now().strftime("%H:%M:%S"), name, label, members, new_total)
            )
            cur.execute("UPDATE event SET total=%s;", (new_total,))
        conn.commit()

    session.pop("member_auth", None)
    return render_template("success.html")

# ---------------- ADMIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/dashboard")
        return render_template("login.html", error="Wrong password")
    return render_template("login.html")

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        update_event(
            active=True,
            name=request.form.get("event"),
            capacity=int(request.form.get("capacity")),
            member_password=request.form.get("member_password")
        )
        return redirect("/dashboard")

    active, name, capacity, mp, total = get_event()
    return render_template("setup.html", event=name, capacity=capacity, member_password=mp)

@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    active, name, capacity, mp, total = get_event()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT time, name, type, members, total FROM logs ORDER BY id DESC;")
            logs = [
                {"time": r[0], "name": r[1], "type": r[2], "members": r[3], "total": r[4]}
                for r in cur.fetchall()
            ]

    return render_template(
        "admin.html",
        event=name,
        total=total,
        max=capacity,
        logs=logs,
        member_password=mp
    )

@app.route("/reset", methods=["POST"])
def reset():
    if not session.get("admin"):
        return redirect("/admin")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM logs;")
            cur.execute("""
                UPDATE event
                SET active=FALSE, name='', capacity=0, member_password='', total=0;
            """)
        conn.commit()

    return redirect("/setup")

@app.route("/export")
def export():
    if not session.get("admin"):
        return redirect("/admin")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT time, name, type, members, total FROM logs;")
            rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Name", "Type", "Members", "Total"])
    for r in rows:
        writer.writerow(r)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="event_entries.csv"
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/admin")

if __name__ == "__main__":
    app.run(debug=True)

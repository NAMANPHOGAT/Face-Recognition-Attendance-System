from flask import Flask, render_template, request, redirect, session
import pandas as pd

app = Flask(__name__)
app.secret_key = "attendance_secret"

ATTENDANCE_FILE = "attendance.xlsx"

# Dummy login credentials (can be Excel-based later)
STUDENTS = {
    "101": "pass101",
    "102": "pass102"
}

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        roll = request.form["roll"]
        password = request.form["password"]

        if roll in STUDENTS and STUDENTS[roll] == password:
            session["roll"] = roll
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "roll" not in session:
        return redirect("/")

    roll = session["roll"]

    df = pd.read_excel(ATTENDANCE_FILE)
    student_data = df[df["Roll No"] == int(roll)]

    records = student_data.to_dict(orient="records")

    return render_template("dashboard.html", records=records, roll=roll)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, request, jsonify, session, send_from_directory
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = "attendance_secret"
CORS(app)


students = {
    "2024272434": {
        "name": "Naman Phogat",
        "email": "studentemail@gmail.com"
    }
}


otp_store = {}

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/style.css")
def style():
    return send_from_directory(".", "style.css")


@app.route("/script.js")
def script():
    return send_from_directory(".", "script.js")


@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    roll = data.get("roll")

    if roll not in students:
        return jsonify({"error": "Invalid Roll Number"}), 400

    email = students[roll]["email"]
    otp = random.randint(100000, 999999)

    otp_store[roll] = {
        "otp": otp,
        "expiry": datetime.now() + timedelta(minutes=2)
    }

    send_email(email, otp)

    return jsonify({"message": "OTP sent to registered email"}), 200



@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    roll = data.get("roll")
    entered_otp = data.get("otp")

    if roll not in otp_store:
        return jsonify({"error": "OTP not found"}), 400

    otp_data = otp_store[roll]

    if datetime.now() > otp_data["expiry"]:
        return jsonify({"error": "OTP expired"}), 400

    if str(otp_data["otp"]) != str(entered_otp):
        return jsonify({"error": "Invalid OTP"}), 400

    session["roll"] = roll
    del otp_store[roll]

    return jsonify({
        "message": "Login successful",
        "name": students[roll]["name"]
    }), 200



def send_email(to_email, otp):
    msg = EmailMessage()
    msg.set_content(f"Your OTP for Attendance Portal is: {otp}")
    msg["Subject"] = "Attendance Portal Login OTP"
    msg["From"] = "yourmail@gmail.com"
    msg["To"] = to_email

    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login("yourmail@gmail.com", "APP_PASSWORD")
    server.send_message(msg)
    server.quit()


if __name__ == "__main__":
    app.run(debug=True)

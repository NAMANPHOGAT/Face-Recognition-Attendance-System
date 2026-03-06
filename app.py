import base64
import importlib.util
import io
import os
import secrets
import smtplib
from smtplib import SMTPAuthenticationError
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from openpyxl import Workbook, load_workbook
from PIL import Image
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        action = request.form.get("action", "login")
        roll = request.form.get("roll", "").strip()
        students = read_students()
        student = students.get(roll)

        if not student:
            return render_template("student_login.html", error="Invalid roll number", roll=roll)

        student_email = student.get("email", "")
        if "@" not in student_email:
            return render_template(
                "student_login.html",
                error="Student email missing in Excel. Update Students sheet column 3.",
                roll=roll,
            )

        if action == "send_otp":
            otp = f"{secrets.randbelow(1_000_000):06d}"
            expiry = datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
            session["pending_student_roll"] = roll
            session["student_otp"] = otp
            session["student_otp_expiry"] = expiry.isoformat()
            try:
                _send_otp(otp, student_email, "Student")
            except Exception as exc:
                return render_template("student_login.html", error=f"OTP sending failed: {exc}", roll=roll)

            return render_template(
                "student_login.html",
                message=f"OTP sent from {OTP_SENDER_EMAIL} to {student_email}.",
                roll=roll,
            )

        entered_otp = request.form.get("otp", "").strip()
        saved_otp = session.get("student_otp")
        saved_roll = session.get("pending_student_roll")
        expiry_str = session.get("student_otp_expiry")

        if not entered_otp or not saved_otp or not expiry_str:
            return render_template("student_login.html", error="Please request OTP first.", roll=roll)

        if saved_roll != roll:
            return render_template("student_login.html", error="OTP belongs to different roll number.", roll=roll)

        if datetime.now() > datetime.fromisoformat(expiry_str):
            return render_template("student_login.html", error="OTP expired. Please request a new OTP.", roll=roll)

        if entered_otp != saved_otp:
            return render_template("student_login.html", error="Invalid OTP", roll=roll)

        session.clear()
        session["student_roll"] = roll
        return redirect(url_for("student_dashboard"))

    return render_template("student_login.html")


@app.route("/student/dashboard")
@student_required
def student_dashboard():
    roll = session["student_roll"]
    records = get_attendance_for_roll(roll)
    return render_template("student_dashboard.html", roll=roll, records=records)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        action = request.form.get("action", "login")
        employee_id = request.form.get("employee_id", "").strip()

        admin_settings = read_admin_settings()
        admin_employee_id = admin_settings["employee_id"]
        otp_receiver = admin_settings["otp_receiver"]

        if employee_id != admin_employee_id:
            return render_template("admin_login.html", error="Invalid employee ID", employee_id=employee_id)

        if action == "send_otp":
            otp = f"{secrets.randbelow(1_000_000):06d}"
            expiry = datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
            session["pending_admin_employee_id"] = employee_id
            session["admin_otp"] = otp
            session["admin_otp_expiry"] = expiry.isoformat()

            try:
                _send_otp(otp, otp_receiver, "Admin")
            except Exception as exc:
                return render_template("admin_login.html", error=f"OTP sending failed: {exc}", employee_id=employee_id)

            return render_template(
                "admin_login.html",
                message=f"OTP sent from {OTP_SENDER_EMAIL} to {otp_receiver}.",
                employee_id=employee_id,
            )

        entered_otp = request.form.get("otp", "").strip()
        saved_otp = session.get("admin_otp")
        saved_employee_id = session.get("pending_admin_employee_id")
        expiry_str = session.get("admin_otp_expiry")

        if not entered_otp or not saved_otp or not expiry_str:
            return render_template("admin_login.html", error="Please request OTP first.", employee_id=employee_id)

        if saved_employee_id != employee_id:
            return render_template("admin_login.html", error="OTP was generated for different employee ID.", employee_id=employee_id)

        if datetime.now() > datetime.fromisoformat(expiry_str):
            return render_template("admin_login.html", error="OTP expired. Please request a new OTP.", employee_id=employee_id)

        if entered_otp != saved_otp:
            return render_template("admin_login.html", error="Invalid OTP", employee_id=employee_id)

        session.clear()
        session["admin_authenticated"] = True
        session["admin_employee_id"] = employee_id
        return redirect(url_for("admin_camera"))

    return render_template("admin_login.html")


@app.route("/admin/camera")
@admin_required
def admin_camera():
    return render_template("admin_camera.html")


@app.route("/admin/recognize", methods=["POST"])
@admin_required
def admin_recognize():
    payload = request.get_json(silent=True) or {}
    image_data = payload.get("image")

    if not image_data:
        return jsonify({"success": False, "message": "Image data is required"}), 400

    try:
        recognized = _recognize_student_from_frame(image_data)
    except RuntimeError as exc:
        return jsonify({"success": False, "message": str(exc)}), 500
    except Exception:
        return jsonify({"success": False, "message": "Unable to process camera frame."}), 400

    if not recognized:
        return jsonify({"success": False, "message": "No known student face matched."})

    entry = mark_attendance(recognized["roll"], recognized["name"])
    return jsonify({"success": True, "message": "Attendance marked successfully.", "attendance": entry})


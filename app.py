import base64
import importlib.util
import io
import os
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from openpyxl import Workbook, load_workbook
from PIL import Image

if importlib.util.find_spec("face_recognition") and importlib.util.find_spec("numpy"):
    import face_recognition
    import numpy as np
else:
    face_recognition = None
    np = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "attendance_secret")

BASE_DIR = Path(__file__).resolve().parent
ATTENDANCE_FILE = BASE_DIR / "attendance.xlsx"
KNOWN_FACES_DIR = BASE_DIR / "known_faces"

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

STUDENT_HEADERS = ["Roll No", "Name", "Password"]
ATTENDANCE_HEADERS = ["Roll No", "Name", "Date", "Time", "Status"]


def _normalize_header(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def _find_sheet_by_headers(workbook, expected_headers: list[str]):
    expected = [_normalize_header(h) for h in expected_headers]
    for sheet in workbook.worksheets:
        first_row = [cell.value for cell in sheet[1]]
        normalized = [_normalize_header(v) for v in first_row]
        if normalized[: len(expected)] == expected:
            return sheet
    return None


def ensure_workbook() -> None:
    """Ensure attendance.xlsx contains Students and Attendance sheets."""
    if ATTENDANCE_FILE.exists():
        wb = load_workbook(ATTENDANCE_FILE)
    else:
        wb = Workbook()

    students_ws = wb["Students"] if "Students" in wb.sheetnames else _find_sheet_by_headers(wb, STUDENT_HEADERS)
    attendance_ws = wb["Attendance"] if "Attendance" in wb.sheetnames else _find_sheet_by_headers(wb, ATTENDANCE_HEADERS)

    if students_ws is None:
        students_ws = wb.create_sheet("Students")
        students_ws.append(STUDENT_HEADERS)
        students_ws.append([101, "Student One", "pass101"])
        students_ws.append([102, "Student Two", "pass102"])
    elif students_ws.title != "Students":
        students_ws.title = "Students"

    if attendance_ws is None:
        attendance_ws = wb.create_sheet("Attendance")
        attendance_ws.append(ATTENDANCE_HEADERS)
    elif attendance_ws.title != "Attendance":
        attendance_ws.title = "Attendance"

    if wb.active.title not in {"Students", "Attendance"}:
        wb.active = wb["Students"]

    wb.save(ATTENDANCE_FILE)


def read_students() -> dict[str, dict[str, str]]:
    ensure_workbook()
    wb = load_workbook(ATTENDANCE_FILE, data_only=True)
    ws = wb["Students"]

    students: dict[str, dict[str, str]] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        roll = str(row[0]).strip()
        students[roll] = {
            "name": str(row[1]).strip() if row[1] else "",
            "password": str(row[2]).strip() if row[2] else "",
        }
    return students


def get_attendance_for_roll(roll: str) -> list[dict[str, str]]:
    ensure_workbook()
    wb = load_workbook(ATTENDANCE_FILE, data_only=True)
    ws = wb["Attendance"]

    records: list[dict[str, str]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or str(row[0]).strip() != str(roll):
            continue
        records.append(
            {
                "date": str(row[2]),
                "time": str(row[3]),
                "status": str(row[4]),
            }
        )
    return records


def mark_attendance(roll: str, name: str) -> dict[str, str]:
    ensure_workbook()
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    wb = load_workbook(ATTENDANCE_FILE)
    ws = wb["Attendance"]
    ws.append([roll, name, date_str, time_str, "Present"])
    wb.save(ATTENDANCE_FILE)

    return {"roll": roll, "name": name, "date": date_str, "time": time_str}


def admin_required(route_func):
    @wraps(route_func)
    def wrapper(*args, **kwargs):
        if session.get("admin_authenticated") is not True:
            return redirect(url_for("admin_login"))
        return route_func(*args, **kwargs)

    return wrapper


def student_required(route_func):
    @wraps(route_func)
    def wrapper(*args, **kwargs):
        if "student_roll" not in session:
            return redirect(url_for("student_login"))
        return route_func(*args, **kwargs)

    return wrapper


def _decode_data_url_to_bytes(data_url: str) -> bytes:
    _, encoded = data_url.split(",", 1) if "," in data_url else ("", data_url)
    if not encoded:
        raise ValueError("Empty image payload")
    return base64.b64decode(encoded)


def _load_known_face_encodings() -> list[dict[str, object]]:
    if face_recognition is None:
        return []

    students = read_students()
    known_faces: list[dict[str, object]] = []

    if not KNOWN_FACES_DIR.exists():
        return known_faces

    for roll, metadata in students.items():
        folder = KNOWN_FACES_DIR / roll
        if not folder.exists() or not folder.is_dir():
            continue

        for image_file in folder.iterdir():
            if image_file.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            image = face_recognition.load_image_file(str(image_file))
            encodings = face_recognition.face_encodings(image)
            if encodings:
                known_faces.append(
                    {"roll": roll, "name": metadata["name"], "encoding": encodings[0]}
                )
    return known_faces


def _recognize_student_from_frame(data_url: str) -> dict[str, str] | None:
    if face_recognition is None or np is None:
        raise RuntimeError(
            "face_recognition dependency is missing. Install packages from requirements.txt"
        )

    payload = _decode_data_url_to_bytes(data_url)
    pil_image = Image.open(io.BytesIO(payload)).convert("RGB")
    frame_encodings = face_recognition.face_encodings(np.array(pil_image))
    if not frame_encodings:
        return None

    known_faces = _load_known_face_encodings()
    if not known_faces:
        return None

    known_encodings = [known["encoding"] for known in known_faces]
    for frame_encoding in frame_encodings:
        distances = face_recognition.face_distance(known_encodings, frame_encoding)
        if len(distances) == 0:
            continue
        best_idx = int(distances.argmin())
        if distances[best_idx] <= 0.45:
            best_match = known_faces[best_idx]
            return {"roll": str(best_match["roll"]), "name": str(best_match["name"])}
    return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        roll = request.form.get("roll", "").strip()
        password = request.form.get("password", "").strip()
        student = read_students().get(roll)

        if student and student["password"] == password:
            session.clear()
            session["student_roll"] = roll
            return redirect(url_for("student_dashboard"))
        return render_template("student_login.html", error="Invalid roll number or password")

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
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["admin_authenticated"] = True
            return redirect(url_for("admin_camera"))
        return render_template("admin_login.html", error="Invalid admin credentials")

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


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    ensure_workbook()
    app.run(debug=True)

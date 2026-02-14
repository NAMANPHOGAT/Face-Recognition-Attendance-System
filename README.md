# Face Recognition Attendance System

This project has two portals:

1. **Admin / Camera Platform**
   - Admin logs in
   - Starts webcam
   - Recognizes student face
   - Marks attendance in **`attendance.xlsx`** (date + time)
2. **Student Portal**
   - Student logs in with roll number + OTP
   - OTP is sent to student email from Excel
   - Views attendance from the same **`attendance.xlsx`** file (read-only)

---

## 1) Prerequisites

- Python **3.10+** (recommended)
- `pip`
- Webcam access (for admin face recognition)

> `face-recognition` may require system libraries (`cmake`, `dlib`, compiler tools) depending on OS.

---

## 2) Setup

From project root:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3) Run the application

```bash
python app.py
```

Then open:

- Home: `http://ip address/`
- Admin login: `http://ip address/admin/login`
- Student login: `http://ip address/student/login`

---

## 4) Default credentials

### Admin
- Employee ID login (default): `EMP001`
- Password is always a one-time OTP sent from `N4manphogat@gmail.com`

Set environment variables before running:
- Admin auth config now comes from the `Admin` sheet in `attendance.xlsx` (`Employee ID`, `OTP Receiver Email`).
- `GMAIL_APP_PASSWORD` (required for SMTP login)

### Students
Student login is OTP-based. Student contact emails are read from the **`Students`** sheet in `attendance.xlsx` (column 3).
Default rows are created if missing:

- Roll: `101`, Email: `student101@example.com`
- Roll: `102`, Email: `student102@example.com`

---

## 5) Face recognition enrollment

Add known face images like this:

```text
known_faces/
  101/
    photo1.jpg
    photo2.jpg
  102/
    photo1.jpg
```

- Folder name must match student **roll number** in `attendance.xlsx`.
- Use clear front-facing photos.

---

## 6) How attendance is stored

All data is in **`attendance.xlsx`** and is always read by the main backend at runtime:

- `Admin` sheet: `Employee ID`, `OTP Receiver Email`
- `Students` sheet: `Roll No`, `Name`, `Email`
- `Attendance` sheet: `Roll No`, `Name`, `Date`, `Time`, `Status`

Only the admin camera route writes attendance rows.
Students can only view their own rows.

---

## 7) Quick troubleshooting

- **`No module named flask`**
  - Activate venv and run `pip install -r requirements.txt`
- **Face recognition dependency missing**
  - Install OS build tools and reinstall `face-recognition`
- **Camera not opening**
  - Allow browser camera permission
  - Use HTTPS/localhost contexts where browser requires secure camera access


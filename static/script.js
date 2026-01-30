const BASE_URL = "http://127.0.0.1:5000";

// SEND OTP
function sendOtp() {
    const roll = document.getElementById("roll").value;

    fetch(`${BASE_URL}/send-otp`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ roll })
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("loginMsg").innerText =
            data.message || data.error;

        if (data.message) {
            document.getElementById("otpBox").classList.remove("hidden");
        }
    });
}

// VERIFY OTP
function verifyOtp() {
    const roll = document.getElementById("roll").value;
    const otp = document.getElementById("otp").value;

    fetch(`${BASE_URL}/verify-otp`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ roll, otp })
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("otpMsg").innerText =
            data.message || data.error;

        if (data.message) {
            document.getElementById("loginBox").classList.add("hidden");
            document.getElementById("otpBox").classList.add("hidden");
            startCamera();
        }
    });
}

// CAMERA START
function startCamera() {
    document.getElementById("faceBox").classList.remove("hidden");

    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            document.getElementById("video").srcObject = stream;
        });
}

// CAPTURE FACE
function captureFace() {
    const video = document.getElementById("video");
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);

    fetch(`${BASE_URL}/face-recognize`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            image: canvas.toDataURL("image/jpeg")
        })
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("faceMsg").innerText = data.message;

        if (data.success) {
            document.getElementById("faceBox").classList.add("hidden");
            document.getElementById("resultBox").classList.remove("hidden");
            document.getElementById("resultText").innerText =
                "Attendance Marked Successfully";
        }
    });
}

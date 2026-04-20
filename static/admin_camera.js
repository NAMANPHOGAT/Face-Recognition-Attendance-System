const video = document.getElementById('video');
const statusText = document.getElementById('statusText');
const startBtn = document.getElementById('startCameraBtn');
const captureBtn = document.getElementById('captureBtn');

let stream;
const MAX_RECOGNITION_ATTEMPTS = 3;

async function startCamera() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        video.srcObject = stream;
        statusText.textContent = 'Camera started. Ready to recognize student.';
    } catch (error) {
        statusText.textContent = `Could not access camera: ${error.message}`;
    }
}

async function captureAndRecognize() {
    if (!stream) {
        statusText.textContent = 'Start camera first.';
        return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    for (let attempt = 1; attempt <= MAX_RECOGNITION_ATTEMPTS; attempt += 1) {
        canvas.getContext('2d').drawImage(video, 0, 0);
        const image = canvas.toDataURL('image/jpeg', 0.9);
        statusText.textContent = `Processing frame ${attempt}/${MAX_RECOGNITION_ATTEMPTS}...`;

        const response = await fetch('/admin/recognize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image })
        });

        const data = await response.json();
        if (response.ok && data.success) {
            statusText.textContent = `${data.message} ${data.attendance.roll} - ${data.attendance.name} at ${data.attendance.time} (${data.attendance.status}) by ${data.attendance.employee_id}`;
            return;
        }

        const message = (data && data.message) ? data.message : 'Could not mark attendance.';
        if (!response.ok) {
            statusText.textContent = message;
            return;
        }

        if (attempt < MAX_RECOGNITION_ATTEMPTS) {
            await new Promise((resolve) => setTimeout(resolve, 250));
            continue;
        }

        statusText.textContent = `${message} Tried ${MAX_RECOGNITION_ATTEMPTS} frames.`;
    }
}

startBtn.addEventListener('click', startCamera);
captureBtn.addEventListener('click', captureAndRecognize);

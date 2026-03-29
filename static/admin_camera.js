const video = document.getElementById('video');
const statusText = document.getElementById('statusText');
const startBtn = document.getElementById('startCameraBtn');
const captureBtn = document.getElementById('captureBtn');

let stream;

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
    canvas.getContext('2d').drawImage(video, 0, 0);

    const image = canvas.toDataURL('image/jpeg');
    statusText.textContent = 'Processing frame and matching face...';

    const response = await fetch('/admin/recognize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image })
    });

    const data = await response.json();
    if (!response.ok || !data.success) {
        statusText.textContent = data.message || 'Could not mark attendance.';
        return;
    }

    statusText.textContent = `${data.message} ${data.attendance.roll} - ${data.attendance.name} at ${data.attendance.time}`;
}

startBtn.addEventListener('click', startCamera);
captureBtn.addEventListener('click', captureAndRecognize);

function sendOtp() {
  const roll = document.getElementById("roll").value;

  fetch("http://localhost:5000/send-otp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ roll })
  });

  document.getElementById("loginBox").classList.add("hidden");
  document.getElementById("otpBox").classList.remove("hidden");
}

function verifyOtp() {
  const roll = document.getElementById("roll").value;
  const otp = document.getElementById("otp").value;

  fetch("http://localhost:5000/verify-otp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ roll, otp })
  }).then(res => {
    if (res.ok) window.location = "/dashboard";
    else alert("Invalid OTP");
  });
}

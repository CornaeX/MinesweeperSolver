let stream = null;
const video = document.getElementById('video');
const resultDiv = document.getElementById('result');

async function startCamera() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment" }  // back camera on tablet
        });
        video.srcObject = stream;
    } catch (err) {
        resultDiv.innerHTML = 'Camera error: ' + err.message;
    }
}

async function capture() {
    if (!stream) {
        resultDiv.innerHTML = 'Start camera first';
        return;
    }
    
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    
    const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
    
    resultDiv.innerHTML = 'Sending to PC...';
    
    try {
        const res = await fetch('http://YOUR_PC_IP:5000/process', {  // ← CHANGE THIS
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({image: dataUrl})
        });
        
        const data = await res.json();
        if (data.status === 'success') {
            let html = `<strong>Board detected!</strong><br>Suggestions:<br>`;
            data.suggestions.forEach(s => {
                html += `Click row ${s[0]}, col ${s[1]} → ${s[2]}<br>`;
            });
            resultDiv.innerHTML = html;
        } else {
            resultDiv.innerHTML = data.message;
        }
    } catch (e) {
        resultDiv.innerHTML = 'Server error. Make sure PC server running on same WiFi.';
    }
}

// Auto start camera
startCamera();
const video = document.getElementById("camera");
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const productContainer = document.getElementById("scanned-products");
const statusEl = document.getElementById("status");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");

let scanInterval = null;
let cameraStream = null;

// Start camera
async function startCamera() {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment" }
        });
        video.srcObject = cameraStream;
        return true;
    } catch (error) {
        statusEl.textContent = "❌Camera access denied";
        statusEl.className = "status idle";
        return false;
    }
}

// Scan one frame
async function scanFrame() {
    if (video.readyState !== video.HAVE_ENOUGH_DATA) return;
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);
    
    canvas.toBlob(async function(blob) {
        const formData = new FormData();
        formData.append("image", blob);
        
        try {
            const response = await fetch("/api/barcode/scan", {
                method: "POST",
                body: formData
            });
            
            const result = await response.json();
            
            if (result.status === "success") {
                statusEl.textContent = "Product Found!";
                statusEl.className = "status scanned";
                // Append new product (not replace)
                appendProduct(result.product);
            } else if (result.status === "duplicate") {
                statusEl.textContent = "Already scanned";
                statusEl.className = "status duplicate";
            } else {
                statusEl.textContent = "Scanning...";
                statusEl.className = "status scanning";
            }
        } catch (error) {
            console.error("Scan error:", error);
        }
    }, "image/jpeg");
}

// Append product (adds to existing list)
function appendProduct(product) {
    const timestamp = new Date().toLocaleTimeString();
    
    const productHTML = `
        <div class="product-card">
            <img src="${product.image || 'https://via.placeholder.com/80'}" 
                 onerror="this.src='https://via.placeholder.com/80'">
            <div style="text-align:left;">
                <h3 style="margin:0;">${product.name || 'Unknown'}</h3>
                <p style="margin:5px 0 0; color:#28a745; font-weight:bold;">KES ${product.price || '0.00'}</p>
                <div class="timestamp"> ${timestamp}</div>
            </div>
        </div>
    `;

    // Insert new product at the top
    productContainer.insertAdjacentHTML('afterbegin', productHTML);
}

// Clear all scanned products
function clearHistory() {
    productContainer.innerHTML = '';
}

// Start scanning
async function startScanning() {
    if (!cameraStream) {
        const started = await startCamera();
        if (!started) return;
    }
    
    if (scanInterval) return;
    
    statusEl.textContent = "🔍 Scanning...";
    statusEl.className = "status scanning";
    startBtn.disabled = true;
    stopBtn.disabled = false;
    
    // Scan immediately then every second
    scanFrame();
    scanInterval = setInterval(scanFrame, 1000);
}

// Stop scanning
function stopScanning() {
    if (scanInterval) {
        clearInterval(scanInterval);
        scanInterval = null;
    }
    
    statusEl.textContent = "⏹ Stopped";
    statusEl.className = "status idle";
    startBtn.disabled = false;
    stopBtn.disabled = true;
}

// Initialize
async function init() {
    await startCamera();
    video.addEventListener("loadedmetadata", () => {
        console.log("Camera ready");
        statusEl.textContent = "Click 'Start Scanning'";
        statusEl.className = "status idle";
    });
}

// Clean up on page unload
window.addEventListener("beforeunload", () => {
    if (scanInterval) {
        clearInterval(scanInterval);
    }
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
    }
});

// Start the app
init();
document.addEventListener("DOMContentLoaded", function() {
    const logContainer = document.getElementById("log-container");
    const socketUrl = `ws://${window.location.host}/ws/logs`;
    let socket;

    function connect() {
        socket = new WebSocket(socketUrl);

        socket.onopen = function(event) {
            console.log("WebSocket connection established.");
            const entry = document.createElement("div");
            entry.className = "log-entry info";
            entry.textContent = "--- WebSocket Connected ---";
            logContainer.appendChild(entry);
        };

        socket.onmessage = function(event) {
            const message = event.data;
            const entry = document.createElement("div");
            
            // Simple parsing to add color based on log level
            const lowerCaseMessage = message.toLowerCase();
            let level = 'info';
            if (lowerCaseMessage.includes('[warning]')) {
                level = 'warning';
            } else if (lowerCaseMessage.includes('[error]')) {
                level = 'error';
            }

            entry.className = `log-entry ${level}`;
            entry.textContent = message;
            logContainer.appendChild(entry);

            // Auto-scroll to the bottom
            logContainer.scrollTop = logContainer.scrollHeight;
        };

        socket.onclose = function(event) {
            console.log("WebSocket connection closed. Reconnecting in 2 seconds...");
            const entry = document.createElement("div");
            entry.className = "log-entry error";
            entry.textContent = "--- WebSocket Disconnected. Attempting to reconnect... ---";
            logContainer.appendChild(entry);
            logContainer.scrollTop = logContainer.scrollHeight;
            setTimeout(connect, 2000);
        };

        socket.onerror = function(error) {
            console.error("WebSocket Error:", error);
        };
    }

    connect();
});

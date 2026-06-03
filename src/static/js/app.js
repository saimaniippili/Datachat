document.addEventListener("DOMContentLoaded", () => {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const uploadStatus = document.getElementById("upload-status");
    
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const chatMessages = document.getElementById("chat-messages");
    
    const statusDot = document.querySelector(".status-dot");
    const connectionStatus = document.getElementById("connection-status");
    
    const modelSelect = document.getElementById("model-select");
    const exportBtn = document.getElementById("export-btn");
    const dataProfile = document.getElementById("data-profile");
    const profileStats = document.getElementById("profile-stats");
    
    const sessionsList = document.getElementById("sessions-list");
    const newChatBtn = document.getElementById("new-chat-btn");
    
    let isConnected = false;
    let selectedModel = "llama3:8b";
    let currentSessionId = null;

    // Modal Logic
    const modal = document.getElementById("image-modal");
    const modalImg = document.getElementById("modal-img");
    const closeModal = document.getElementsByClassName("close-modal")[0];

    closeModal.onclick = function() {
        modal.style.display = "none";
    }
    
    // Close modal on outside click
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    }

    // Fetch models on load
    fetch("/api/models")
        .then(res => res.json())
        .then(data => {
            modelSelect.innerHTML = "";
            data.models.forEach(model => {
                const option = document.createElement("option");
                option.value = model;
                option.textContent = model;
                if(model === "llama3:8b") option.selected = true;
                modelSelect.appendChild(option);
            });
            if (modelSelect.value) selectedModel = modelSelect.value;
        })
        .catch(err => {
            modelSelect.innerHTML = "<option value='llama3:8b'>llama3:8b</option>";
        });

    modelSelect.addEventListener("change", (e) => {
        selectedModel = e.target.value;
    });

    // Fetch sessions on load
    loadSessions();

    function loadSessions() {
        fetch("/api/sessions")
            .then(res => res.json())
            .then(data => {
                sessionsList.innerHTML = "";
                if (data.sessions.length === 0) {
                    sessionsList.innerHTML = '<div style="padding:10px; font-weight:600;">No past chats found.</div>';
                    return;
                }
                
                data.sessions.forEach(session => {
                    const el = document.createElement("div");
                    el.className = "session-item neo-border";
                    if (session.id === currentSessionId) el.classList.add("active");
                    
                    const date = new Date(session.created_at).toLocaleString();
                    el.textContent = `${session.filename} (${date})`;
                    
                    el.title = `${session.filename} (${date})`;
                    
                    el.addEventListener("click", () => selectSession(session.id));
                    sessionsList.appendChild(el);
                });
            });
    }

    function selectSession(sessionId) {
        currentSessionId = sessionId;
        
        // Update UI styles
        Array.from(sessionsList.children).forEach(child => {
            child.classList.remove("active");
        });
        
        // Disable chat initially
        setConnectionState(false, "Loading Session...");
        
        fetch(`/api/sessions/${sessionId}`)
            .then(res => {
                if (!res.ok) throw new Error("Failed to load session");
                return res.json();
            })
            .then(data => {
                // Render messages
                chatMessages.innerHTML = "";
                
                if (data.messages.length === 0) {
                    addMessage("assistant", "Session loaded. Ask me anything about this data!");
                } else {
                    data.messages.forEach(msg => {
                        addMessage(msg.role, msg.content);
                    });
                }
                
                // Render profile
                if (data.profile) {
                    renderProfile(data.profile);
                } else {
                    dataProfile.style.display = 'none';
                }
                
                // Re-fetch sessions to update active class accurately
                loadSessions();
                
                setConnectionState(true, "Ready");
            })
            .catch(err => {
                console.error(err);
                setConnectionState(false, "Error Loading Session");
            });
    }

    newChatBtn.addEventListener("click", () => {
        currentSessionId = null;
        chatMessages.innerHTML = `
            <div class="message assistant">
                <div class="message-bubble neo-border">
                    Upload a dataset to start a new chat! Or select a previous chat from the sidebar.
                </div>
            </div>
        `;
        dataProfile.style.display = 'none';
        setConnectionState(false, "Upload Data to Start");
        loadSessions();
    });

    // Drag & Drop
    dropZone.addEventListener("click", () => fileInput.click());
    
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.style.transform = "scale(1.02)";
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.style.transform = "scale(1)";
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.style.transform = "scale(1)";
        if (e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length) {
            handleFileUpload(e.target.files[0]);
        }
    });

    function handleFileUpload(file) {
        const formData = new FormData();
        formData.append("file", file);
        
        uploadStatus.textContent = "Uploading and processing...";
        
        fetch("/api/upload", {
            method: "POST",
            body: formData
        })
        .then(response => {
            if (!response.ok) throw new Error("Upload failed");
            return response.json();
        })
        .then(data => {
            uploadStatus.textContent = data.message;
            currentSessionId = data.session_id;
            
            chatMessages.innerHTML = "";
            addMessage("assistant", `I've loaded ${data.filename}! What would you like to know about it?`);
            
            setConnectionState(true, "Ready");
            
            renderProfile(data.profile);
            loadSessions(); // refresh sidebar
            
            setTimeout(() => {
                uploadStatus.textContent = "";
            }, 3000);
        })
        .catch(error => {
            uploadStatus.textContent = `Error: ${error.message}`;
            setConnectionState(false, "Upload Failed");
        });
    }
    
    function renderProfile(profile) {
        profileStats.innerHTML = `
            <strong>Rows:</strong> ${profile.rows} <br>
            <strong>Columns:</strong> ${profile.cols} <br>
            <strong>Features:</strong> ${profile.columns.map(c => c.name).join(", ")}
        `;
        dataProfile.style.display = 'block';
    }

    function setConnectionState(connected, text) {
        isConnected = connected;
        
        if (connected) {
            statusDot.classList.add("connected");
            connectionStatus.textContent = text;
            chatInput.disabled = false;
            sendBtn.disabled = false;
        } else {
            statusDot.classList.remove("connected");
            connectionStatus.textContent = text;
            chatInput.disabled = true;
            sendBtn.disabled = true;
        }
    }

    function addMessage(role, text) {
        const messageDiv = document.createElement("div");
        messageDiv.className = `message ${role}`;
        
        const bubble = document.createElement("div");
        bubble.className = "message-bubble neo-border";
        
        bubble.innerHTML = marked.parse(text);
        
        // Cache bust images and add preview button
        const imgs = bubble.querySelectorAll('img');
        imgs.forEach(img => {
            if(img.src.includes('temp_chart.png')) {
                img.src = img.src.split('?')[0] + '?t=' + new Date().getTime();
            }
            
            // Wrap image in a container for relative positioning
            const imgWrapper = document.createElement("div");
            imgWrapper.style.position = "relative";
            imgWrapper.style.display = "inline-block";
            imgWrapper.style.maxWidth = "100%";
            imgWrapper.style.marginTop = "15px";
            
            // Add Expand Button overlay
            const expandBtn = document.createElement("button");
            expandBtn.innerHTML = "⛶"; // Expand icon
            expandBtn.className = "expand-btn";
            
            expandBtn.onclick = function(e) {
                e.stopPropagation();
                modal.style.display = "block";
                modalImg.src = img.src;
            }
            
            img.style.cursor = "pointer";
            img.title = "Click to enlarge";
            // Remove the margin-top from the image itself since the wrapper handles it
            img.style.marginTop = "0"; 
            img.onclick = expandBtn.onclick;
            
            // Insert wrapper and move image inside
            img.parentNode.insertBefore(imgWrapper, img);
            imgWrapper.appendChild(img);
            imgWrapper.appendChild(expandBtn);
        });
        
        messageDiv.appendChild(bubble);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || !currentSessionId) return;
        
        addMessage("user", text);
        chatInput.value = "";
        
        const originalStatus = connectionStatus.textContent;
        setConnectionState(false, "Analyzing...");
        
        fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                session_id: currentSessionId,
                prompt: text, 
                model_name: selectedModel 
            })
        })
        .then(response => {
            if (!response.ok) throw new Error("Network response was not ok");
            return response.json();
        })
        .then(data => {
            addMessage("assistant", data.response);
            setConnectionState(true, "Ready");
        })
        .catch(error => {
            addMessage("assistant", `Sorry, there was an error processing your request: ${error.message}`);
            setConnectionState(true, "Ready");
        });
    }

    sendBtn.addEventListener("click", sendMessage);
    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            sendMessage();
        }
    });
    
    exportBtn.addEventListener("click", () => {
        if(!currentSessionId) {
            alert("No active session to export!");
            return;
        }
        
        const htmlContent = document.documentElement.outerHTML;
        
        const styleMatch = htmlContent.match(/<style[^>]*>[\s\S]*?<\/style>|<link[^>]*rel="stylesheet"[^>]*>/gi);
        const styles = styleMatch ? styleMatch.join('\\n') : '';
        
        const exportHTML = `
            <!DOCTYPE html>
            <html>
            <head>
                <title>DataChat Export Report</title>
                ${styles}
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap" rel="stylesheet">
            </head>
            <body style="padding: 40px; background-color: #f0f0f0;">
                <h1 style="margin-bottom: 20px;">📊 DataChat Analysis Report</h1>
                <div class="profile-card neo-border">
                    ${dataProfile.innerHTML}
                </div>
                <div class="chat-container neo-border" style="padding: 20px;">
                    ${chatMessages.innerHTML}
                </div>
            </body>
            </html>
        `;
        
        const blob = new Blob([exportHTML], {type: 'text/html'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'datachat_report.html';
        a.click();
        URL.revokeObjectURL(url);
    });
});

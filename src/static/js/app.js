// Update this to your Render URL when deploying to Vercel (e.g., "https://my-app.onrender.com")
const BACKEND_URL = "https://datachat-0vvd.onrender.com";

document.addEventListener("DOMContentLoaded", () => {
    // UI Elements
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const uploadStatus = document.getElementById("upload-status");
    
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const chatMessages = document.getElementById("chat-messages");
    const welcomeScreen = document.getElementById("welcome-screen");
    
    const connectionStatus = document.getElementById("connection-status");
    const modelSelect = document.getElementById("model-select");
    const exportBtn = document.getElementById("export-btn");
    
    const sessionsList = document.getElementById("sessions-list");
    const newChatBtn = document.getElementById("new-chat-btn");
    
    // Settings Modal Elements
    const openSettingsBtn = document.getElementById("open-settings-btn");
    const settingsModal = document.getElementById("settings-modal");
    const closeSettingsBtn = document.getElementById("close-settings-btn");
    const testConnectionBtn = document.getElementById("test-connection-btn");
    const saveSettingsBtn = document.getElementById("save-settings-btn");
    const apiBaseUrlInput = document.getElementById("api-base-url");
    const apiKeyInput = document.getElementById("api-key");
    const connectionTestResult = document.getElementById("connection-test-result");
    
    // Image Modal Elements
    const imageModal = document.getElementById("image-modal");
    const modalImg = document.getElementById("modal-img");
    const closeImageModal = document.getElementsByClassName("close-image-modal")[0];

    // State
    let isConnected = false;
    let selectedModel = "";
    let currentSessionId = null;

    // --- Settings & API Key Logic ---
    
    // Load saved settings
    const savedApiKey = localStorage.getItem("dataChatApiKey") || "";
    const savedApiBase = localStorage.getItem("dataChatApiBase") || "https://integrate.api.nvidia.com/v1";
    apiKeyInput.value = savedApiKey;
    apiBaseUrlInput.value = savedApiBase;

    // (Auth logic removed)
    loadSessions();

    openSettingsBtn.addEventListener("click", (e) => {
        e.preventDefault();
        settingsModal.classList.remove("hidden");
    });

    closeSettingsBtn.addEventListener("click", () => {
        settingsModal.classList.add("hidden");
        connectionTestResult.classList.add("hidden");
    });

    // Test Connection
    testConnectionBtn.addEventListener("click", async () => {
        const apiKey = apiKeyInput.value.trim();
        const apiBase = apiBaseUrlInput.value.trim();
        
        if (!apiKey) {
            connectionTestResult.textContent = "Please enter an API Key.";
            connectionTestResult.className = "mt-4 text-sm text-red-400 block";
            return;
        }

        testConnectionBtn.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Testing...';
        testConnectionBtn.disabled = true;

        try {
            const res = await fetch(BACKEND_URL + "/api/check_connection", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ api_key: apiKey, api_base_url: apiBase })
            });
            const data = await res.json();
            
            if (res.ok && data.status === "success") {
                connectionTestResult.innerHTML = '<i class="ph-fill ph-check-circle"></i> Connection successful!';
                connectionTestResult.className = "mt-4 text-sm text-green-400 block";
            } else {
                throw new Error(data.detail || "Connection failed");
            }
        } catch (error) {
            connectionTestResult.innerHTML = `<i class="ph-fill ph-warning-circle"></i> ${error.message}`;
            connectionTestResult.className = "mt-4 text-sm text-red-400 block";
        } finally {
            testConnectionBtn.innerHTML = '<i class="ph ph-plugs-connected"></i> Test Connection';
            testConnectionBtn.disabled = false;
        }
    });

    saveSettingsBtn.addEventListener("click", () => {
        localStorage.setItem("dataChatApiKey", apiKeyInput.value.trim());
        localStorage.setItem("dataChatApiBase", apiBaseUrlInput.value.trim());
        settingsModal.classList.add("hidden");
    });


    // --- Core App Logic ---
    
    // Modals outside click
    window.onclick = function(event) {
        if (event.target == imageModal) imageModal.classList.add("hidden");
        if (event.target == settingsModal) settingsModal.classList.add("hidden");
    }
    closeImageModal.onclick = () => imageModal.classList.add("hidden");

    // Fetch models on load
    fetch(BACKEND_URL + "/api/models")
        .then(res => res.json())
        .then(data => {
            modelSelect.innerHTML = "";
            data.models.forEach((model, index) => {
                const option = document.createElement("option");
                option.value = model;
                option.textContent = model.toUpperCase();
                if (index === 0) {
                    option.selected = true;
                    selectedModel = model;
                }
                modelSelect.appendChild(option);
            });
            if (modelSelect.value) selectedModel = modelSelect.value;
        })
        .catch(err => {
            modelSelect.innerHTML = "<option value='nvidia/nemotron-3-ultra-550b-a55b'>NVIDIA/NEMOTRON-3</option>";
            selectedModel = "nvidia/nemotron-3-ultra-550b-a55b";
        });

    modelSelect.addEventListener("change", (e) => {
        selectedModel = e.target.value;
    });

    // Fetch sessions on load
    loadSessions();

    function loadSessions() {
        fetch(BACKEND_URL + "/api/sessions")
            .then(res => res.json())
            .then(data => {
                sessionsList.innerHTML = "";
                if (data.sessions.length === 0) {
                    sessionsList.innerHTML = '<div class="text-xs text-gray-500 p-2">No past chats found.</div>';
                    return;
                }
                
                data.sessions.forEach(session => {
                    const el = document.createElement("div");
                    el.className = "session-item";
                    if (session.id === currentSessionId) el.classList.add("active");
                    
                    const date = new Date(session.created_at).toLocaleString();
                    
                    el.innerHTML = `
                        <i class="ph ph-file-csv"></i>
                        <div style="display:flex; flex-direction:column;">
                            <span style="font-weight:500; color:var(--text-primary); font-size:0.85rem;">${session.filename}</span>
                            <span style="font-size:0.7rem;">${date}</span>
                        </div>
                    `;
                    
                    el.addEventListener("click", () => selectSession(session.id));
                    sessionsList.appendChild(el);
                });
            });
    }

    function selectSession(sessionId) {
        currentSessionId = sessionId;
        
        Array.from(sessionsList.children).forEach(child => {
            child.classList.remove("active");
        });
        
        fetch(BACKEND_URL + `/api/sessions/${sessionId}`)
            .then(res => res.json())
            .then(data => {
                if (data.error) return;
                
                chatMessages.innerHTML = "";
                welcomeScreen.classList.add("hidden");
                chatMessages.classList.remove("hidden");
                
                data.messages.forEach(msg => {
                    addMessage(msg.role, msg.content, true);
                });
                
                renderProfile(data.profile);
                
                setConnectionState(true, "Ready");
                loadSessions(); 
            });
    }

    // New Chat
    newChatBtn.addEventListener("click", () => {
        currentSessionId = null;
        chatMessages.innerHTML = "";
        welcomeScreen.classList.remove("hidden");
        chatMessages.classList.add("hidden");
        renderProfile(null);
        setConnectionState(false, "Upload Data to Start");
        loadSessions();
    });

    // Drag & Drop
    dropZone.addEventListener("click", () => fileInput.click());
    
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.style.transform = "translateZ(10px) scale(1.02)";
        dropZone.style.borderColor = "var(--primary)";
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.style.transform = "translateZ(0) scale(1)";
        dropZone.style.borderColor = "var(--border)";
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.style.transform = "translateZ(0) scale(1)";
        dropZone.style.borderColor = "var(--border)";
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
        
        fetch(BACKEND_URL + "/api/upload", {
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
            welcomeScreen.classList.add("hidden");
            chatMessages.classList.remove("hidden");
            
            addMessage("assistant", `I've loaded ${data.filename}! What would you like to know about it?`);
            
            renderProfile(data.profile);
            
            setConnectionState(true, "Ready");
            
            loadSessions();
            
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
        const profilePanel = document.getElementById("dataset-profile-panel");
        const statsEl = document.getElementById("dataset-stats");
        const colsEl = document.getElementById("dataset-columns");
        
        if (!profile) {
            if (profilePanel) profilePanel.classList.add("hidden");
            return;
        }
        
        if (profilePanel) {
            profilePanel.classList.remove("hidden");
            statsEl.textContent = `${profile.rows.toLocaleString()} rows • ${profile.cols} columns`;
            
            colsEl.innerHTML = "";
            profile.columns.forEach(col => {
                const div = document.createElement("div");
                div.className = "column-item";
                div.innerHTML = `
                    <span class="column-name" title="${col.name}">${col.name}</span>
                    <span class="column-type">${col.type}</span>
                `;
                colsEl.appendChild(div);
            });
        }
    }

    function setConnectionState(connected, text) {
        isConnected = connected;
        
        if (connected) {
            connectionStatus.textContent = text;
            connectionStatus.className = "connection-status-text text-center mt-2 text-xs text-green-400";
            chatInput.disabled = false;
            sendBtn.disabled = false;
        } else {
            connectionStatus.textContent = text;
            connectionStatus.className = "connection-status-text text-center mt-2 text-xs text-gray-500";
            chatInput.disabled = true;
            sendBtn.disabled = true;
        }
    }

    function addMessage(role, text, skipCacheBust=false) {
        const messageDiv = document.createElement("div");
        messageDiv.className = `message ${role}`;
        
        const bubble = document.createElement("div");
        bubble.className = "message-bubble";
        
        bubble.innerHTML = marked.parse(text);
        
        const imgs = bubble.querySelectorAll('img');
        imgs.forEach(img => {
            if(!skipCacheBust && img.src.includes('temp_chart.png')) {
                img.src = img.src.split('?')[0] + '?t=' + new Date().getTime();
            }
            
            // Only add wrapper if not already wrapped (to prevent double wrapping on re-renders)
            if (!img.parentNode.classList.contains('chart-wrapper')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'chart-wrapper';
                
                img.parentNode.insertBefore(wrapper, img);
                
                const downloadBtn = document.createElement('a');
                downloadBtn.className = 'chart-download-btn no-print';
                downloadBtn.href = img.src;
                downloadBtn.download = `DataChat_Chart_${new Date().getTime()}.png`;
                downloadBtn.title = "Download chart";
                downloadBtn.innerHTML = '<i class="ph ph-download-simple"></i>';
                
                wrapper.appendChild(downloadBtn);
                wrapper.appendChild(img);
            }
            
            img.style.cursor = "pointer";
            img.title = "Click to enlarge";
            img.onclick = function(e) {
                e.stopPropagation();
                imageModal.classList.remove("hidden");
                modalImg.src = img.src;
            }
        });
        
        messageDiv.appendChild(bubble);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function sendMessage(textToOverwrite = null) {
        const text = textToOverwrite || chatInput.value.trim();
        if (!text || !currentSessionId) return;
        
        addMessage("user", text);
        chatInput.value = "";
        
        setConnectionState(false, "Processing...");
        
        // Add typing indicator
        const typingIndicator = document.createElement("div");
        typingIndicator.className = "message assistant typing-message";
        typingIndicator.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        chatMessages.appendChild(typingIndicator);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Grab API Keys from LocalStorage to send to backend
        const key = localStorage.getItem("dataChatApiKey") || null;
        const base = localStorage.getItem("dataChatApiBase") || null;

        fetch(BACKEND_URL + "/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                session_id: currentSessionId,
                prompt: text, 
                model_name: selectedModel,
                api_key: key,
                api_base_url: base
            })
        })
        .then(response => {
            if (!response.ok) throw new Error("Network response was not ok");
            return response.json();
        })
        .then(data => {
            typingIndicator.remove();
            addMessage("assistant", data.response);
            setConnectionState(true, "Ready");
        })
        .catch(error => {
            typingIndicator.remove();
            addMessage("assistant", "Sorry, an error occurred while processing your request.");
            setConnectionState(true, "Error occurred");
        });
    }

    sendBtn.addEventListener("click", () => sendMessage());

    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Wire up quick-action buttons (Insights Toolkit)
    const toolBtns = document.querySelectorAll('.tool-btn');
    toolBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            if (!currentSessionId) {
                alert("Please upload a dataset first.");
                return;
            }
            const actionType = btn.textContent.trim();
            const promptMap = {
                "Summary": "Provide a comprehensive statistical summary of the dataset.",
                "Correlation": "Analyze the correlations between the numerical columns in this dataset and display a heatmap if possible.",
                "Trends": "What are the key trends over time in this dataset?",
                "Outliers": "Detect and list any significant outliers in the data.",
                "Clusters": "Can you identify any natural groupings or clusters in this data?",
                "Forecast": "Based on the historical data, what is a simple forecast for the main metric?"
            };
            
            if (promptMap[actionType]) {
                sendMessage(promptMap[actionType]);
            }
        });
    });
    
    // Wire up suggestion chips
    const chips = document.querySelectorAll('.chip');
    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            chatInput.value = chip.textContent.trim();
        });
    });

    // Theme Toggle
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    if (themeToggleBtn) {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            themeToggleBtn.innerHTML = '<i class="ph ph-sun"></i>';
        }
        
        themeToggleBtn.addEventListener('click', () => {
            if (document.documentElement.getAttribute('data-theme') === 'dark') {
                document.documentElement.removeAttribute('data-theme');
                localStorage.setItem('theme', 'light');
                themeToggleBtn.innerHTML = '<i class="ph ph-moon"></i>';
            } else {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
                themeToggleBtn.innerHTML = '<i class="ph ph-sun"></i>';
            }
        });
    }

    // PDF Export
    exportBtn.addEventListener("click", () => {
        if (!currentSessionId) {
            alert("No active chat to export.");
            return;
        }

        const messages = chatMessages.querySelectorAll('.message');
        if (messages.length === 0) return;

        exportBtn.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Exporting...';
        
        let htmlContent = `
            <style>
                .pdf-container img {
                    page-break-inside: avoid !important;
                    display: block;
                    max-width: 100%;
                    margin: 15px auto;
                }
                .pdf-container p, .pdf-container h1, .pdf-container h2, .pdf-container h3 {
                    page-break-inside: avoid !important;
                }
                .pdf-container pre, .pdf-container table {
                    page-break-inside: avoid !important;
                }
                .no-print { display: none !important; }
            </style>
            <div class="pdf-container" style="font-family: Arial, sans-serif; padding: 40px; color: #1f2937;">
                <h1 style="color: #6366f1; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; margin-bottom: 30px;">
                    Data Analysis Report
                </h1>
        `;

        messages.forEach(msg => {
            if (msg.classList.contains("typing-message")) return;

            const isUser = msg.classList.contains("user");
            const bubble = msg.querySelector('.message-bubble').innerHTML;

            if (isUser) {
                htmlContent += `
                    <div style="margin-bottom: 25px; page-break-inside: avoid;">
                        <div style="font-weight: bold; color: #6b7280; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">Question</div>
                        <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; font-size: 14px;">
                            ${bubble}
                        </div>
                    </div>
                `;
            } else {
                htmlContent += `
                    <div style="margin-bottom: 40px; page-break-inside: avoid;">
                        <div style="font-weight: bold; color: #6366f1; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">Analysis</div>
                        <div style="font-size: 14px; line-height: 1.6;">
                            ${bubble}
                        </div>
                    </div>
                `;
            }
        });

        htmlContent += `
                <div style="margin-top: 50px; font-size: 11px; color: #9ca3af; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 20px;">
                    Generated by DataChat AI • ${new Date().toLocaleString()}
                </div>
            </div>
        `;

        const opt = {
            margin:       0.5,
            filename:     'Data_Analysis_Report.pdf',
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2, useCORS: true },
            jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' },
            pagebreak:    { mode: ['css', 'legacy'] }
        };

        // Pass the HTML string directly to html2pdf to avoid viewport clipping issues (blank PDF)
        html2pdf().set(opt).from(htmlContent).save().then(() => {
            exportBtn.innerHTML = '<i class="ph ph-trend-up"></i> Export Report';
        });
    });
});

/* ========================================
   My Agent - Chat UI
   ======================================== */

let currentSessionId = null;
let sessions = [];
let lastComplexTaskResult = null;

function toggleSubtaskPanel() {
    const panel = document.getElementById('subtaskPanel');
    panel.classList.toggle('open');

    if (!panel.classList.contains('open')) {
        return;
    }

    if (lastComplexTaskResult) {
        renderSubtasks(lastComplexTaskResult);
        return;
    }

    const latestComplexTask = findLatestComplexTask();
    if (latestComplexTask) {
        renderSubtasks(latestComplexTask);
        return;
    }

    document.getElementById('subtaskList').innerHTML = '<p class="subtask-empty">No task details yet. Run a complex task to inspect decomposition and execution progress here.</p>';
}

function findLatestComplexTask() {
    const container = document.getElementById('chatContainer');
    const messages = container.querySelectorAll('.message.assistant');

    for (let i = messages.length - 1; i >= 0; i -= 1) {
        const contentDiv = messages[i].querySelector('.message-content');
        if (!contentDiv || !contentDiv.dataset.subtasks) {
            continue;
        }

        try {
            const subtasks = JSON.parse(contentDiv.dataset.subtasks);
            return {
                sub_tasks: subtasks,
                duration: parseFloat(contentDiv.dataset.totalDuration) || 0,
                parallel_efficiency: parseFloat(contentDiv.dataset.parallelEfficiency) || 0,
            };
        } catch (error) {
            console.error('Failed to parse subtask metadata:', error);
        }
    }

    return null;
}

function renderSubtasks(result) {
    const list = document.getElementById('subtaskList');

    if (!result || !result.sub_tasks || result.sub_tasks.length === 0) {
        list.innerHTML = '<p class="subtask-empty">No task data available.</p>';
        return;
    }

    list.innerHTML = result.sub_tasks.map((task, index) => {
        const statusClass = task.status === 'completed' || task.status === 'success'
            ? 'success'
            : task.status === 'failed'
                ? 'failed'
                : 'running';

        const statusText = task.status === 'completed' || task.status === 'success'
            ? 'Success'
            : task.status === 'failed'
                ? 'Failed'
                : 'Running';

        const taskName = task.task_id || `Task ${index + 1}`;

        return `
            <div class="subtask-item">
                <div class="subtask-status ${statusClass}">${statusText}</div>
                <div class="subtask-title">${taskName}</div>
                <div class="subtask-meta">${(task.duration || 0).toFixed(1)}s | ${task.result_length || 0} chars</div>
                <div class="subtask-preview">${task.result_preview || 'No preview available yet.'}</div>
            </div>
        `;
    }).join('');
}

function showSubtasksForMessage(metadata) {
    lastComplexTaskResult = {
        sub_tasks: metadata.sub_tasks,
        duration: metadata.total_duration,
        parallel_efficiency: metadata.parallel_efficiency,
    };

    const subtaskBtn = document.getElementById('modeSubtask');
    if (subtaskBtn) {
        subtaskBtn.style.display = 'inline-flex';
    }

    const panel = document.getElementById('subtaskPanel');
    if (!panel.classList.contains('open')) {
        panel.classList.add('open');
    }

    renderSubtasks(lastComplexTaskResult);
}

async function loadSessions() {
    try {
        const token = localStorage.getItem('authToken');
        const response = await fetch(`${API_BASE_URL}/api/v1/sessions`, {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        if (response.status === 401) {
            localStorage.removeItem('authToken');
            localStorage.removeItem('currentUser');
            window.location.href = 'login.html';
            return;
        }

        sessions = await response.json();
        renderSessionList();
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

function renderSessionList() {
    const container = document.getElementById('sessionList');

    if (sessions.length === 0) {
        container.innerHTML = '<div class="subtask-empty">No sessions yet. Start a new conversation to build your workspace history.</div>';
        return;
    }

    container.innerHTML = sessions.map((session) => `
        <div class="session-item ${session.session_id === currentSessionId ? 'active' : ''}" onclick="selectSession('${session.session_id}')">
            <div class="session-info">
                <div class="session-title">${session.title}</div>
                <div class="session-time">Updated ${formatTime(session.updated_at)}</div>
            </div>
            <button
                type="button"
                class="session-delete"
                onclick="deleteSession(event, '${session.session_id}')"
                title="Delete session"
                aria-label="Delete session"
            >
                X
            </button>
        </div>
    `).join('');
}

async function createNewSession() {
    currentSessionId = null;
    const chatTitleEl = document.getElementById('chatTitle');
    const chatSubtitleEl = document.getElementById('chatSubtitle');
    chatTitleEl.style.display = 'none';
    chatTitleEl.textContent = '';
    if (chatSubtitleEl) {
        chatSubtitleEl.textContent = 'Ask one focused question, upload working files, and keep every session traceable.';
    }

    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-badge">Ready</div>
            <div class="empty-state-icon">AI</div>
            <h3 id="welcomeTitle">Professional AI Workspace</h3>
            <p id="welcomeDesc">Upload a PDF or image, reference the file path in your prompt, and let the assistant work inside a persistent conversation.</p>
            <div class="empty-state-grid">
                <div class="empty-state-card">
                    <span class="empty-state-card-title">Structured Sessions</span>
                    <p>Each conversation is saved, reloadable, and separated by user identity.</p>
                </div>
                <div class="empty-state-card">
                    <span class="empty-state-card-title">Multimodal Intake</span>
                    <p>Attach PDF and image inputs directly, then continue analysis in one thread.</p>
                </div>
                <div class="empty-state-card">
                    <span class="empty-state-card-title">Long-Task Support</span>
                    <p>Complex prompts can be decomposed into tracked subtasks with visible progress.</p>
                </div>
            </div>
        </div>
    `;

    renderSessionList();
    document.getElementById('messageInput').focus();
}

async function selectSession(sessionId) {
    currentSessionId = sessionId;

    try {
        const token = localStorage.getItem('authToken');
        const response = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        if (response.status === 401) {
            localStorage.removeItem('authToken');
            localStorage.removeItem('currentUser');
            window.location.href = 'login.html';
            return;
        }

        const session = await response.json();
        const chatTitleEl = document.getElementById('chatTitle');
        const chatSubtitleEl = document.getElementById('chatSubtitle');
        chatTitleEl.textContent = session.title;
        chatTitleEl.style.display = 'block';
        if (chatSubtitleEl) {
            chatSubtitleEl.textContent = `${session.messages.length} messages in this thread. Continue the conversation or add a file-backed request.`;
        }

        const container = document.getElementById('chatContainer');
        container.innerHTML = '';

        session.messages.forEach((message) => {
            addMessage(message.role, message.content, false, message.metadata);
        });

        renderSessionList();
        scrollToBottom();
    } catch (error) {
        console.error('Failed to load session:', error);
    }
}

async function deleteSession(event, sessionId) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    if (!confirm('Delete this session?')) {
        return;
    }

    try {
        const token = localStorage.getItem('authToken');
        const response = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
            method: 'DELETE',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        if (response.status === 401) {
            localStorage.removeItem('authToken');
            localStorage.removeItem('currentUser');
            window.location.href = 'login.html';
            return;
        }

        if (!response.ok) {
            throw new Error(`Delete failed: ${response.status}`);
        }

        if (currentSessionId === sessionId) {
            await createNewSession();
        }

        await loadSessions();
    } catch (error) {
        console.error('Delete session failed:', error);
    }
}

function showChatTitleForCurrentSession() {
    if (!currentSessionId) {
        return;
    }

    const session = sessions.find((item) => item.session_id === currentSessionId);
    if (!session) {
        return;
    }

    const chatTitleEl = document.getElementById('chatTitle');
    chatTitleEl.textContent = session.title;
    chatTitleEl.style.display = 'block';
}

function useExample(exampleText) {
    const input = document.getElementById('messageInput');
    input.value = exampleText;
    input.focus();
    autoResize(input);
}

function triggerFileUpload() {
    const input = document.getElementById('fileUploadInput');
    if (input) {
        input.click();
    }
}

async function handleFileUpload(event) {
    const fileInput = event.target;
    const uploadBtn = document.getElementById('uploadBtn');
    const file = fileInput.files && fileInput.files[0];

    if (!file) {
        return;
    }

    const token = localStorage.getItem('authToken');
    const formData = new FormData();
    formData.append('file', file);

    uploadBtn.disabled = true;
    setUploadStatus(`Uploading ${file.name} ...`);

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/uploads`, {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${token}`,
            },
            body: formData,
        });

        if (response.status === 401) {
            localStorage.removeItem('authToken');
            localStorage.removeItem('currentUser');
            window.location.href = 'login.html';
            return;
        }

        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.detail || result.error || 'Upload failed');
        }

        const input = document.getElementById('messageInput');
        const promptLine = result.file_type === 'pdf'
            ? `Please analyze this PDF file: ${result.relative_path}`
            : `Please analyze this image file: ${result.relative_path}`;

        input.value = input.value ? `${input.value}\n${promptLine}` : promptLine;
        autoResize(input);
        setUploadStatus(`Uploaded ${result.filename} -> ${result.relative_path}`, 'success');
    } catch (error) {
        console.error('File upload failed:', error);
        setUploadStatus(`Upload failed: ${error.message}`, 'error');
    } finally {
        uploadBtn.disabled = false;
        fileInput.value = '';
    }
}

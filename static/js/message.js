/* ========================================
   My Agent - Message Send and Stream Handling
   ======================================== */

const LOCAL_IMAGE_PATH_PATTERN = /(?:data\/uploads\/images\/[^\s)\]"'`]+\.(?:png|jpg|jpeg|webp)|\/uploads\/images\/[^\s)\]"'`]+\.(?:png|jpg|jpeg|webp))/gi;

function normalizeImageUrl(rawPath) {
    if (!rawPath) {
        return null;
    }

    const cleaned = rawPath.trim().replace(/^['"`]+|['"`]+$/g, '');
    if (cleaned.startsWith('/uploads/')) {
        return `${API_BASE_URL}${cleaned}`;
    }
    if (cleaned.startsWith('data/uploads/')) {
        return `${API_BASE_URL}/${cleaned.replace(/^data\/uploads/, 'uploads')}`;
    }
    return null;
}

function buildImagePreviewHtml(content) {
    const matches = content.match(LOCAL_IMAGE_PATH_PATTERN) || [];
    const uniquePaths = [...new Set(matches.map((item) => item.trim()))];

    if (uniquePaths.length === 0) {
        return '';
    }

    const cards = uniquePaths.map((imagePath) => {
        const imageUrl = normalizeImageUrl(imagePath);
        if (!imageUrl) {
            return '';
        }
        const safePath = imagePath.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return `
            <div class="generated-image-card">
                <a class="generated-image-link" href="${imageUrl}" target="_blank" rel="noopener noreferrer">${safePath}</a>
                <img class="generated-image-preview" src="${imageUrl}" alt="Generated image preview" loading="lazy" />
            </div>
        `;
    }).filter(Boolean).join('');

    return cards ? `<div class="generated-image-gallery">${cards}</div>` : '';
}

function renderAssistantContent(contentDiv, content) {
    const markdownHtml = typeof marked !== 'undefined' ? marked.parse(content) : content;
    contentDiv.innerHTML = `${markdownHtml}${buildImagePreviewHtml(content)}`;
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const message = input.value.trim();

    if (!message) return;

    input.value = '';
    input.style.height = 'auto';

    addMessage('user', message);

    const assistantDiv = addMessage('assistant', '', false);
    const contentDiv = assistantDiv.querySelector('.message-content');
    contentDiv.innerHTML = '<span style="color: #64748b;">Thinking</span><span class="cursor">...</span>';

    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="loading"></span>';

    try {
        const token = localStorage.getItem('authToken');
        await handleUnifiedStream(message, contentDiv, token);
    } catch (error) {
        console.error('Error:', error);
        contentDiv.textContent = `Error: ${error.message}`;
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<span class="send-btn-icon">^</span>';
        document.getElementById('messageInput').focus();
    }
}

async function handleUnifiedStream(message, contentDiv, token) {
    const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            message,
            session_id: currentSessionId
        })
    });

    if (response.status === 401) {
        localStorage.removeItem('authToken');
        localStorage.removeItem('currentUser');
        window.location.href = 'login.html';
        return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';
    let sessionId = null;
    let isComplex = false;
    const subTasks = [];

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);

            if (data === '[DONE]') continue;

            if (data.startsWith('__SESSION_ID__:')) {
                sessionId = data.replace('__SESSION_ID__:', '');
                if (!currentSessionId) {
                    currentSessionId = sessionId;
                    await loadSessions();
                    showChatTitleForCurrentSession();
                }
                continue;
            }

            let jsonData = null;
            try {
                jsonData = JSON.parse(data);
            } catch (error) {
                jsonData = null;
            }

            if (jsonData && jsonData.type) {
                if (jsonData.type === 'routing' && jsonData.data?.mode === 'complex') {
                    isComplex = true;
                    contentDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #64748b;">Starting analysis...</div>';
                    continue;
                }

                if (isComplex) {
                    handleComplexEvent(jsonData, contentDiv, subTasks);
                    continue;
                }
            }

            if (!isComplex) {
                fullText += data;
                if (typeof marked !== 'undefined') {
                    const previewHtml = buildImagePreviewHtml(fullText);
                    contentDiv.innerHTML = `${marked.parse(fullText)}${previewHtml}<span class="cursor">|</span>`;
                } else {
                    contentDiv.textContent = fullText + '|';
                }
                scrollToBottom();
            }
        }
    }

    if (!isComplex) {
        if (typeof marked !== 'undefined') {
            renderAssistantContent(contentDiv, fullText);
        } else {
            contentDiv.textContent = fullText;
        }
    }
}

function handleComplexEvent(event, contentDiv, subTasks) {
    switch (event.type) {
        case 'decompose_start':
            contentDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #64748b;">Breaking down the task...</div>';
            break;

        case 'decompose_complete': {
            const taskCount = event.data.sub_tasks_count;
            contentDiv.innerHTML = `<div style="padding: 20px;">
                <div style="margin-bottom: 12px; padding: 14px; background: #eff6ff; border-radius: 14px; color: #1e3a8a;">
                    <strong>Task decomposition complete</strong><br>
                    <span style="font-size: 13px; color: #475569;">Split into ${taskCount} subtasks for parallel execution</span>
                </div>
                <div id="subtaskProgress"></div>
            </div>`;
            break;
        }

        case 'subtask_start':
            subTasks.push({
                id: event.data.task_id,
                name: event.data.task_name || event.data.task_id,
                status: 'running',
                duration: 0,
                result_length: 0
            });
            renderSubtaskProgress(contentDiv, subTasks);
            break;

        case 'subtask_complete': {
            const task = subTasks.find((item) => item.id === event.data.task_id);
            if (task) {
                task.status = 'success';
                task.duration = event.data.duration;
                task.result_length = event.data.result_length;
            }
            renderSubtaskProgress(contentDiv, subTasks);
            break;
        }

        case 'subtask_failed': {
            const failedTask = subTasks.find((item) => item.id === event.data.task_id);
            if (failedTask) {
                failedTask.status = 'failed';
                failedTask.error = event.data.error;
            }
            renderSubtaskProgress(contentDiv, subTasks);
            break;
        }

        case 'execution_complete':
            break;

        case 'synthesis_start': {
            const synthDiv = document.createElement('div');
            synthDiv.id = 'synthesisStatus';
            synthDiv.style.cssText = 'margin-top: 12px; padding: 14px; background: #eff6ff; border-radius: 14px; color: #475569;';
            synthDiv.textContent = 'Building the final answer...';
            contentDiv.appendChild(synthDiv);
            scrollToBottom();
            break;
        }

        case 'final_result': {
            const result = event.data;

            lastComplexTaskResult = {
                sub_tasks: result.sub_tasks,
                duration: result.duration,
                parallel_efficiency: result.parallel_efficiency || 0
            };

            const subtaskBtn = document.getElementById('modeSubtask');
            if (subtaskBtn) subtaskBtn.style.display = 'inline-flex';

            if (result.session_id && !currentSessionId) {
                currentSessionId = result.session_id;
                loadSessions().then(() => showChatTitleForCurrentSession());
            }

            if (!result.success && !result.reply) {
                contentDiv.innerHTML = '<div style="color: #c2410c; padding: 16px;">Task failed: all subtasks failed. Check API quota and retry.</div>';
                break;
            }

            let html = '<div style="padding: 10px 0;">';
            html += '<div style="margin-bottom: 16px; padding: 14px; background: #eff6ff; border-radius: 14px; border: 1px solid rgba(37, 99, 235, 0.12);">';
            html += '<strong>Analysis result</strong><br>';
            html += '<span style="font-size: 13px; color: #475569;">';
            html += `Total time: ${(result.duration || 0).toFixed(1)}s | `;
            html += `Subtasks: ${result.sub_tasks?.length || 0}`;
            if (result.parallel_efficiency) {
                html += ` | Parallel efficiency: ${(result.parallel_efficiency * 100).toFixed(1)}%`;
            }
            html += '</span></div>';

            if (typeof marked !== 'undefined') {
                html += `${marked.parse(result.reply || '')}${buildImagePreviewHtml(result.reply || '')}`;
            } else {
                html += `<pre>${result.reply || ''}</pre>`;
            }
            html += '</div>';
            contentDiv.innerHTML = html;
            scrollToBottom();
            break;
        }

        case 'error':
            contentDiv.innerHTML = `<div style="color: #c2410c; padding: 16px;">Task failed: ${event.data.error}</div>`;
            break;
    }
}

function renderSubtaskProgress(contentDiv, subTasks) {
    const progressDiv = contentDiv.querySelector('#subtaskProgress');
    if (!progressDiv) return;

    progressDiv.innerHTML = subTasks.map((task) => {
        const statusIcon = task.status === 'running' ? '...' : task.status === 'success' ? 'OK' : 'X';
        const statusText = task.status === 'running'
            ? 'Running...'
            : task.status === 'success'
                ? `Done (${task.duration.toFixed(1)}s)`
                : 'Failed';

        return `
            <div style="padding: 10px 12px; margin: 6px 0; background: white; border-radius: 12px; border: 1px solid rgba(148, 163, 184, 0.16); border-left: 3px solid ${task.status === 'running' ? '#f59e0b' : task.status === 'success' ? '#13795b' : '#c2410c'};">
                <span style="margin-right: 8px;">${statusIcon}</span>
                <strong>${task.name}</strong>
                <span style="float: right; font-size: 12px; color: #64748b;">${statusText}</span>
            </div>
        `;
    }).join('');
}

function addMessage(role, content, scroll = true, metadata = null) {
    const container = document.getElementById('chatContainer');

    const emptyState = container.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? 'YOU' : 'AI';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (role === 'assistant' && metadata && metadata.is_complex_task) {
        const subtaskBtn = document.createElement('button');
        subtaskBtn.className = 'view-subtasks-btn';
        subtaskBtn.innerHTML = 'Tasks';
        subtaskBtn.title = 'View subtasks';
        subtaskBtn.onclick = () => {
            showSubtasksForMessage(metadata);
        };
        contentDiv.appendChild(subtaskBtn);

        contentDiv.dataset.subtasks = JSON.stringify(metadata.sub_tasks);
        contentDiv.dataset.totalDuration = metadata.total_duration || 0;
        contentDiv.dataset.parallelEfficiency = metadata.parallel_efficiency || 0;
    }

    if (role === 'assistant') {
        renderAssistantContent(contentDiv, content);
    } else {
        contentDiv.textContent = content;
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    container.appendChild(messageDiv);

    if (scroll) {
        scrollToBottom();
    }

    return messageDiv;
}

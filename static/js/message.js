/* ========================================
   My Agent - 消息发送与接收
   ======================================== */

// 发送消息（统一入口，自动路由）
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const message = input.value.trim();

    if (!message) return;

    // 清空输入框
    input.value = '';
    input.style.height = 'auto';

    // 显示用户消息
    addMessage('user', message);

    // 创建 AI 消息占位
    const assistantDiv = addMessage('assistant', '', false);
    const contentDiv = assistantDiv.querySelector('.message-content');
    contentDiv.innerHTML = '<span style="color: #999;">正在思考中</span><span class="cursor">...</span>';

    // 禁用按钮
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="loading"></span>';

    try {
        const token = localStorage.getItem('authToken');
        await handleUnifiedStream(message, contentDiv, token);
    } catch (error) {
        console.error('Error:', error);
        contentDiv.textContent = `❌ 出错了：${error.message}`;
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '发送';
        document.getElementById('messageInput').focus();
    }
}

// 统一流式响应处理（自动识别简单/复杂）
async function handleUnifiedStream(message, contentDiv, token) {
    const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            message: message,
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
    let subTasks = [];
    let complexEvents = [];

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);

            if (data === '[DONE]') continue;

            // 处理会话 ID
            if (data.startsWith('__SESSION_ID__:')) {
                sessionId = data.replace('__SESSION_ID__:', '');
                if (!currentSessionId) {
                    currentSessionId = sessionId;
                    await loadSessions();
                    showChatTitleForCurrentSession();
                }
                continue;
            }

            // 尝试解析 JSON 事件
            let jsonData = null;
            try {
                jsonData = JSON.parse(data);
            } catch (e) {
                // 非 JSON，当作文本内容
            }

            if (jsonData && jsonData.type) {
                // 路由事件：后端告知这是复杂任务
                if (jsonData.type === 'routing' && jsonData.data?.mode === 'complex') {
                    isComplex = true;
                    contentDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">🚀 正在启动智能分析系统...</div>';
                    continue;
                }

                // 复杂任务事件处理
                if (isComplex) {
                    complexEvents.push(jsonData);
                    handleComplexEvent(jsonData, contentDiv, subTasks);
                    continue;
                }
            }

            // 普通文本内容（简单查询）
            if (!isComplex) {
                fullText += data;
                if (typeof marked !== 'undefined') {
                    contentDiv.innerHTML = marked.parse(fullText) + '<span class="cursor">▌</span>';
                } else {
                    contentDiv.textContent = fullText + '▌';
                }
                scrollToBottom();
            }
        }
    }

    // 流结束后最终渲染
    if (isComplex) {
        // 复杂任务已在事件处理中渲染
    } else {
        if (typeof marked !== 'undefined') {
            contentDiv.innerHTML = marked.parse(fullText);
        } else {
            contentDiv.textContent = fullText;
        }
    }
}

// 处理复杂任务事件
function handleComplexEvent(event, contentDiv, subTasks) {
    switch (event.type) {
        case 'decompose_start':
            contentDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">🔪 正在分解任务...</div>';
            break;

        case 'decompose_complete':
            const taskCount = event.data.sub_tasks_count;
            contentDiv.innerHTML = `<div style="padding: 20px;">
                <div style="margin-bottom: 12px; padding: 12px; background: #e3f2fd; border-radius: 8px;">
                    <strong>📋 任务分解完成</strong><br>
                    <span style="font-size: 13px; color: #666;">将分解为 ${taskCount} 个子任务并行执行</span>
                </div>
                <div id="subtaskProgress"></div>
            </div>`;
            break;

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

        case 'subtask_complete':
            const task = subTasks.find(t => t.id === event.data.task_id);
            if (task) {
                task.status = 'success';
                task.duration = event.data.duration;
                task.result_length = event.data.result_length;
            }
            renderSubtaskProgress(contentDiv, subTasks);
            break;

        case 'subtask_failed':
            const failedTask = subTasks.find(t => t.id === event.data.task_id);
            if (failedTask) {
                failedTask.status = 'failed';
                failedTask.error = event.data.error;
            }
            renderSubtaskProgress(contentDiv, subTasks);
            break;

        case 'execution_complete':
            break;

        case 'synthesis_start':
            const synthDiv = document.createElement('div');
            synthDiv.id = 'synthesisStatus';
            synthDiv.style.cssText = 'margin-top: 12px; padding: 12px; background: #f3e5f5; border-radius: 8px; color: #666;';
            synthDiv.textContent = '🔗 正在合成最终结果...';
            contentDiv.appendChild(synthDiv);
            scrollToBottom();
            break;

        case 'final_result':
            const result = event.data;

            // 保存复杂任务结果
            lastComplexTaskResult = {
                sub_tasks: result.sub_tasks,
                duration: result.duration,
                parallel_efficiency: result.parallel_efficiency || 0
            };

            // 显示子任务按钮
            const subtaskBtn = document.getElementById('modeSubtask');
            if (subtaskBtn) subtaskBtn.style.display = 'block';

            // 更新会话 ID
            if (result.session_id && !currentSessionId) {
                currentSessionId = result.session_id;
                loadSessions().then(() => showChatTitleForCurrentSession());
            }

            // 失败且无内容时显示错误
            if (!result.success && !result.reply) {
                contentDiv.innerHTML = `<div style="color: #e53e3e; padding: 16px;">❌ 任务失败：所有子任务执行失败，请检查 API 配额后重试</div>`;
                break;
            }

            // 渲染最终结果
            let html = `<div style="padding: 10px 0;">`;
            html += `<div style="margin-bottom: 16px; padding: 12px; background: #f0f8ff; border-radius: 8px; border-left: 4px solid #667eea;">`;
            html += `<strong>🚀 智能分析结果</strong><br>`;
            html += `<span style="font-size: 13px; color: #666;">`;
            html += `⏱️ 总耗时: ${(result.duration || 0).toFixed(1)}s | `;
            html += `📋 子任务: ${result.sub_tasks?.length || 0}`;
            if (result.parallel_efficiency) {
                html += ` | ⚡ 并行效率: ${(result.parallel_efficiency * 100).toFixed(1)}%`;
            }
            html += `</span></div>`;

            if (typeof marked !== 'undefined') {
                html += marked.parse(result.reply || '');
            } else {
                html += `<pre>${result.reply || ''}</pre>`;
            }
            html += `</div>`;
            contentDiv.innerHTML = html;
            scrollToBottom();
            break;

        case 'error':
            contentDiv.innerHTML = `<div style="color: #e53e3e; padding: 16px;">❌ 任务失败：${event.data.error}</div>`;
            break;
    }
}

// 渲染子任务进度
function renderSubtaskProgress(contentDiv, subTasks) {
    const progressDiv = contentDiv.querySelector('#subtaskProgress');
    if (!progressDiv) return;
    
    progressDiv.innerHTML = subTasks.map(task => {
        const statusIcon = task.status === 'running' ? '⏳' : 
                          task.status === 'success' ? '✅' : '❌';
        const statusText = task.status === 'running' ? '执行中...' : 
                          task.status === 'success' ? `完成 (${task.duration.toFixed(1)}s)` : '失败';
        
        return `
            <div style="padding: 8px 12px; margin: 4px 0; background: white; border-radius: 6px; border-left: 3px solid ${task.status === 'running' ? '#ffc107' : task.status === 'success' ? '#4caf50' : '#f44336'};">
                <span style="margin-right: 8px;">${statusIcon}</span>
                <strong>${task.name}</strong>
                <span style="float: right; font-size: 12px; color: #999;">${statusText}</span>
            </div>
        `;
    }).join('');
}

// 修改 addMessage 函数，返回元素引用
function addMessage(role, content, scroll = true, metadata = null) {
    const container = document.getElementById('chatContainer');

    // 移除空状态
    const emptyState = container.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // 如果是 AI 消息且有子任务元数据，添加查看按钮
    if (role === 'assistant' && metadata && metadata.is_complex_task) {
        const subtaskBtn = document.createElement('button');
        subtaskBtn.className = 'view-subtasks-btn';
        subtaskBtn.innerHTML = '📋';
        subtaskBtn.title = '查看子任务';
        subtaskBtn.onclick = () => {
            showSubtasksForMessage(metadata);
        };
        contentDiv.appendChild(subtaskBtn);
                    
        // 保存完整的子任务数据到元素（包括统计信息）
        contentDiv.dataset.subtasks = JSON.stringify(metadata.sub_tasks);
        contentDiv.dataset.totalDuration = metadata.total_duration || 0;
        contentDiv.dataset.parallelEfficiency = metadata.parallel_efficiency || 0;
    }
    
    // 使用 marked 渲染 Markdown
    if (role === 'assistant') {
        contentDiv.innerHTML += marked.parse(content);
    } else {
        contentDiv.textContent = content;
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    container.appendChild(messageDiv);

    if (scroll) {
        scrollToBottom();
    }

    return messageDiv;  // ← 返回元素引用
}

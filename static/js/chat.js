/* ========================================
   My Agent - 对话功能
   ======================================== */

let currentSessionId = null;
let sessions = [];
let lastComplexTaskResult = null; // 保存最近的复杂任务结果

// 切换子任务面板
function toggleSubtaskPanel() {
    const panel = document.getElementById('subtaskPanel');
    panel.classList.toggle('open');
    
    if (panel.classList.contains('open')) {
        // 优先使用 lastComplexTaskResult
        if (lastComplexTaskResult) {
            renderSubtasks(lastComplexTaskResult);
        } else {
            // 如果没有，查找最近一次的复杂任务消息
            const latestComplexTask = findLatestComplexTask();
            if (latestComplexTask) {
                renderSubtasks(latestComplexTask);
            } else {
                // 没有数据时显示提示
                document.getElementById('subtaskList').innerHTML = `
                    <div style="text-align: center; padding: 40px 20px; color: #999;">
                        <div style="font-size: 48px; margin-bottom: 16px;">📋</div>
                        <p style="font-size: 16px; margin-bottom: 8px;">暂无子任务数据</p>
                        <p style="font-size: 13px;">请先执行一个复杂任务（如产业链分析、对比研究等）</p>
                    </div>
                `;
            }
        }
    }
}

// 查找最近一次的复杂任务
function findLatestComplexTask() {
    const container = document.getElementById('chatContainer');
    const messages = container.querySelectorAll('.message.assistant');
    
    // 从后往前找（最新的）
    for (let i = messages.length - 1; i >= 0; i--) {
        const contentDiv = messages[i].querySelector('.message-content');
        if (contentDiv && contentDiv.dataset.subtasks) {
            try {
                const subtasks = JSON.parse(contentDiv.dataset.subtasks);
                return {
                    sub_tasks: subtasks,
                    duration: parseFloat(contentDiv.dataset.totalDuration) || 0,
                    parallel_efficiency: parseFloat(contentDiv.dataset.parallelEfficiency) || 0
                };
            } catch (e) {
                console.error('解析子任务数据失败:', e);
            }
        }
    }
    
    return null;
}

// 渲染子任务列表
function renderSubtasks(result) {
    const list = document.getElementById('subtaskList');
            
    if (!result || !result.sub_tasks || result.sub_tasks.length === 0) {
        list.innerHTML = '<p style="color: #999; text-align: center; padding: 40px 0;">暂无子任务</p>';
        return;
    }
            
    list.innerHTML = result.sub_tasks.map((task, index) => {
        const statusClass = task.status === 'completed' || task.status === 'success' ? 'success' : 
                           task.status === 'failed' ? 'failed' : 'running';
        const statusText = task.status === 'completed' || task.status === 'success' ? '✅ 成功' : 
                          task.status === 'failed' ? '❌ 失败' : '⏳ 运行中';
                
        // 使用 task_id 作为显示名称（因为后端没有返回 task_name）
        const taskName = task.task_id || `子任务 ${index + 1}`;
                
        return `
            <div class="subtask-item">
                <div class="subtask-status ${statusClass}">${statusText}</div>
                <div class="subtask-title">${taskName}</div>
                <div class="subtask-meta">
                    ⏱️ ${(task.duration || 0).toFixed(1)}s | 📝 ${task.result_length || 0} 字符
                </div>
                <div class="subtask-preview">
                    ${task.result_preview || '无预览'}
                </div>
            </div>
        `;
    }).join('');
}

// 显示指定消息的子任务
function showSubtasksForMessage(metadata) {
    lastComplexTaskResult = {
        sub_tasks: metadata.sub_tasks,
        duration: metadata.total_duration,
        parallel_efficiency: metadata.parallel_efficiency
    };
    
    // 显示子任务按钮
    const subtaskBtn = document.getElementById('modeSubtask');
    if (subtaskBtn) subtaskBtn.style.display = 'block';
    
    // 打开子任务面板
    const panel = document.getElementById('subtaskPanel');
    if (!panel.classList.contains('open')) {
        panel.classList.add('open');
    }
    
    // 渲染子任务
    renderSubtasks(lastComplexTaskResult);
}

// 加载会话列表
async function loadSessions() {
    try {
        const token = localStorage.getItem('authToken');
        const response = await fetch(`${API_BASE_URL}/api/v1/sessions`,
            {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            }
        );

        // 如果后端返回 401，跳转登录页
        if (response.status === 401) {
            window.location.href = 'login.html';
            return;
        }

        sessions = await response.json();
        renderSessionList();
    } catch (error) {
        console.error('加载会话失败:', error);
    }
}

// 渲染会话列表
function renderSessionList() {
    const container = document.getElementById('sessionList');

    if (sessions.length === 0) {
        container.innerHTML = '<div style="text-align: center; color: #999; padding: 20px;">暂无会话</div>';
        return;
    }

    container.innerHTML = sessions.map(session => `
        <div class="session-item ${session.session_id === currentSessionId ? 'active' : ''}"
             onclick="selectSession('${session.session_id}')">
            <div class="session-info">
                <div class="session-title">${session.title}</div>
                <div class="session-time">${formatTime(session.updated_at)}</div>
            </div>
            <button class="session-delete" onclick="event.stopPropagation(); deleteSession('${session.session_id}')" title="删除会话">
                ×
            </button>
        </div>
    `).join('');
}

// 创建新对话
async function createNewSession() {
    currentSessionId = null;
    const chatTitleEl = document.getElementById('chatTitle');
    chatTitleEl.style.display = 'none';
    chatTitleEl.textContent = '';
    
    // 显示完整的留白区域
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">🦌</div>
            <h3 id="welcomeTitle">你好！我是你的 AI 助手</h3>
            <p id="welcomeDesc">我可以帮你搜索信息、分析产业链、处理数据，复杂任务会自动启用智能分析</p>
        </div>
    `;
    
    renderSessionList();
    document.getElementById('messageInput').focus();
}

// 选择会话
async function selectSession(sessionId) {
    currentSessionId = sessionId;

    try {
        const token = localStorage.getItem('authToken');
        const response = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`,
            {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

        // 如果后端返回 401，跳转登录页
        if (response.status === 401) {
            window.location.href = 'login.html';
            return;
        }

        const session = await response.json();

        const chatTitleEl = document.getElementById('chatTitle');
        chatTitleEl.textContent = session.title;
        chatTitleEl.style.display = 'block';

        const container = document.getElementById('chatContainer');
        container.innerHTML = '';

        session.messages.forEach(msg => {
            addMessage(msg.role, msg.content, false, msg.metadata);
        });

        renderSessionList();
        scrollToBottom();
    } catch (error) {
        console.error('加载会话失败:', error);
    }
}

// 删除会话
async function deleteSession(sessionId) {
    if (!confirm('确定要删除这个会话吗？')) return;

    try {
        const token = localStorage.getItem('authToken');
        console.log('删除会话:', sessionId);
        const response = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
            method: 'DELETE',
            headers: {
                    'Authorization': `Bearer ${token}`
                }
        });

        if (response.status === 401) {
            window.location.href = 'login.html';
            return;
        }

        if (currentSessionId === sessionId) {
            createNewSession();
        }

        await loadSessions();
    } catch (error) {
        console.error('删除会话失败:', error);
    }
}

// 根据当前会话显示标题
function showChatTitleForCurrentSession() {
    if (!currentSessionId) return;
    const session = sessions.find(s => s.session_id === currentSessionId);
    if (session) {
        const chatTitleEl = document.getElementById('chatTitle');
        chatTitleEl.textContent = session.title;
        chatTitleEl.style.display = 'block';
    }
}

// 使用示例（点击能力卡片或资讯）
function useExample(exampleText) {
    const input = document.getElementById('messageInput');
    input.value = exampleText;
    input.focus();
    autoResize(input);
}

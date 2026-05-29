/* ========================================
   My Agent - 对话功能
   ======================================== */

let currentSessionId = null;
let sessions = [];
let currentMode = 'normal'; // 'normal' 或 'complex'
let lastComplexTaskResult = null; // 保存最近的复杂任务结果

// 切换模式
function switchMode(mode) {
    currentMode = mode;
    
    // 更新按钮状态
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    if (mode === 'normal') {
        document.getElementById('modeNormal').classList.add('active');
        document.getElementById('modeSubtask').style.display = 'none';
    } else if (mode === 'complex') {
        document.getElementById('modeComplex').classList.add('active');
        
        // 检查当前会话是否有复杂任务消息
        const hasComplexTask = checkCurrentSessionForComplexTasks();
        
        if (hasComplexTask || lastComplexTaskResult) {
            document.getElementById('modeSubtask').style.display = 'block';
        } else {
            document.getElementById('modeSubtask').style.display = 'none';
        }
    }
    
    // 更新欢迎文本
    updateWelcomeText(mode);
    
    console.log(`切换到 ${mode} 模式`);
}

// 更新欢迎文本
function updateWelcomeText(mode) {
    const welcomeTitle = document.getElementById('welcomeTitle');
    const welcomeDesc = document.getElementById('welcomeDesc');
    const modeHint = document.getElementById('modeHint');
    
    if (mode === 'normal') {
        welcomeTitle.textContent = '你好！我是你的 AI 助手';
        welcomeDesc.textContent = '我可以帮你分析网页、处理数据、搜索信息，完成各种复杂任务';
        modeHint.style.display = 'flex';  // 显示模式切换提示
    } else if (mode === 'complex') {
        welcomeTitle.textContent = '🚀 复杂任务模式已启用';
        welcomeDesc.textContent = '我会将复杂任务自动分解为多个子任务，并行执行，智能整合结果';
        modeHint.style.display = 'none';  // 隐藏模式切换提示
    }
}

// 检查当前会话是否有复杂任务
function checkCurrentSessionForComplexTasks() {
    const container = document.getElementById('chatContainer');
    const messages = container.querySelectorAll('.message.assistant');
    
    for (const msg of messages) {
        const contentDiv = msg.querySelector('.message-content');
        if (contentDiv && contentDiv.dataset.subtasks) {
            return true;
        }
    }
    
    return false;
}

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
                        <p style="font-size: 13px;">请先在"复杂任务"模式下执行一个任务</p>
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
    document.getElementById('modeSubtask').style.display = 'block';
    
    // 切换到复杂任务模式
    switchMode('complex');
    
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
    document.getElementById('chatTitle').textContent = '新对话';
    
    // 显示完整的留白区域
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">🦌</div>
            <h3 id="welcomeTitle">你好！我是你的 AI 助手</h3>
            <p id="welcomeDesc">我可以帮你分析网页、处理数据、搜索信息，完成各种复杂任务</p>
            
            <!-- 模式切换提示 -->
            <div class="mode-hint" id="modeHint">
                <span class="mode-hint-icon">💡</span>
                <span class="mode-hint-text">如果有复杂任务（多维度分析、对比研究等），可以切换到</span>
                <button class="mode-hint-btn" onclick="switchMode('complex')">🚀 复杂模式</button>
            </div>
        </div>
    `;
    
    // 更新欢迎文本（根据当前模式）
    updateWelcomeText(currentMode);
    
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

        document.getElementById('chatTitle').textContent = session.title;

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

// 使用示例（点击能力卡片或资讯）
function useExample(exampleText, mode = 'normal') {
    const input = document.getElementById('messageInput');
    input.value = exampleText;
    input.focus();
    autoResize(input);
    
    // 如果需要切换模式
    if (mode === 'complex' && currentMode !== 'complex') {
        switchMode('complex');
    } else if (mode === 'normal' && currentMode !== 'normal') {
        switchMode('normal');
    }
}

/* ========================================
   My Agent - 消息发送与接收
   ======================================== */

// 发送消息（流式）
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
    contentDiv.innerHTML = '<span style="color: #999;">正在思考中</span><span class="cursor">...</span>';  // 友好提示

    // 禁用按钮
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="loading"></span>';

    try {
        const token = localStorage.getItem('authToken');
        
        // 根据模式选择不同的 API
        if (currentMode === 'complex') {
            // 复杂任务模式 - 非流式
            await sendComplexTask(message, contentDiv, sendBtn, token);
        } else {
            // 普通对话模式 - 流式
            await sendNormalMessage(message, contentDiv, sendBtn, token);
        }
    } catch (error) {
        console.error('Error:', error);
        contentDiv.textContent = `❌ 出错了：${error.message}`;
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '发送';
        document.getElementById('messageInput').focus();
    }
}

// 发送普通消息（流式）
async function sendNormalMessage(message, contentDiv, sendBtn, token) {
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
        window.location.href = 'login.html';
        return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';
    let sessionId = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = line.slice(6);

                if (data.startsWith('__SESSION_ID__:')) {
                    sessionId = data.replace('__SESSION_ID__:', '');
                    if (!currentSessionId) {
                        currentSessionId = sessionId;
                        await loadSessions();
                    }
                } else {
                    fullText += data;
                    if (typeof marked !== 'undefined') {
                        const rendered = marked.parse(fullText);
                        contentDiv.innerHTML = rendered + '<span class="cursor">▌</span>';
                    } else {
                        contentDiv.textContent = fullText + '▌';
                    }
                    scrollToBottom();
                }
            }
        }
    }

    if (typeof marked !== 'undefined') {
        contentDiv.innerHTML = marked.parse(fullText);
    } else {
        contentDiv.textContent = fullText;
    }
}

// 发送复杂任务（流式）
async function sendComplexTask(message, contentDiv, sendBtn, token) {
    contentDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">🚀 正在启动 Sub-Agent 编排系统...</div>';
    
    const response = await fetch(`${API_BASE_URL}/api/v1/complex-chat/stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            task: message,
            session_id: currentSessionId,
            decomposition_strategy: 'auto'
        })
    });

    if (response.status === 401) {
        window.location.href = 'login.html';
        return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let subTasks = [];
    let finalResult = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = line.slice(6);
                
                if (data === '[DONE]') continue;
                
                try {
                    const event = JSON.parse(data);
                    
                    // 根据不同事件类型更新 UI
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
                            
                        case 'execution_start':
                            // 开始执行子任务
                            break;
                            
                        case 'subtask_start':
                            // 添加子任务到列表
                            subTasks.push({
                                id: event.data.task_id,
                                name: event.data.task_name,
                                status: 'running',
                                duration: 0,
                                result_length: 0
                            });
                            renderSubtaskProgress(contentDiv, subTasks);
                            break;
                            
                        case 'subtask_complete':
                            // 更新子任务状态
                            const task = subTasks.find(t => t.id === event.data.task_id);
                            if (task) {
                                task.status = 'success';
                                task.duration = event.data.duration;
                                task.result_length = event.data.result_length;
                            }
                            renderSubtaskProgress(contentDiv, subTasks);
                            break;
                            
                        case 'subtask_failed':
                            // 更新子任务为失败
                            const failedTask = subTasks.find(t => t.id === event.data.task_id);
                            if (failedTask) {
                                failedTask.status = 'failed';
                                failedTask.error = event.data.error;
                            }
                            renderSubtaskProgress(contentDiv, subTasks);
                            break;
                            
                        case 'execution_complete':
                            contentDiv.innerHTML += `<div style="margin-top: 12px; padding: 12px; background: #fff3e0; border-radius: 8px;">
                                <strong>✅ 所有子任务执行完成</strong><br>
                                <span style="font-size: 13px; color: #666;">成功: ${event.data.success_count}/${event.data.total_count}</span>
                            </div>`;
                            break;
                            
                        case 'synthesis_start':
                            contentDiv.innerHTML += '<div style="margin-top: 12px; padding: 12px; background: #f3e5f5; border-radius: 8px; color: #666;">🔗 正在合成最终结果...</div>';
                            break;
                            
                        case 'synthesis_complete':
                            contentDiv.innerHTML += `<div style="margin-top: 12px; padding: 12px; background: #e8f5e9; border-radius: 8px; color: #666;">✅ 结果合成完成 (${event.data.result_length} 字符)</div>`;
                            break;
                            
                        case 'final_result':
                            finalResult = event.data;
                            
                            // 保存复杂任务结果
                            lastComplexTaskResult = {
                                sub_tasks: finalResult.sub_tasks,
                                duration: finalResult.duration,
                                parallel_efficiency: finalResult.parallel_efficiency
                            };
                            
                            // 显示子任务按钮
                            document.getElementById('modeSubtask').style.display = 'block';
                            
                            // 渲染最终结果
                            let html = `<div style="padding: 10px 0;">`;
                            html += `<div style="margin-bottom: 16px; padding: 12px; background: #f0f8ff; border-radius: 8px; border-left: 4px solid #667eea;">`;
                            html += `<strong>🚀 Sub-Agent 编排结果</strong><br>`;
                            html += `<span style="font-size: 13px; color: #666;">`;
                            html += `⏱️ 总耗时: ${finalResult.duration.toFixed(1)}s | `;
                            html += `📊 子任务: ${finalResult.sub_tasks.length} | `;
                            html += `✅ 成功: ${finalResult.sub_tasks.filter(t => t.status === 'success').length} | `;
                            html += `⚡ 并行效率: ${(finalResult.parallel_efficiency * 100).toFixed(1)}%`;
                            html += `</span></div>`;
                            
                            // 渲染 Markdown 内容
                            if (typeof marked !== 'undefined') {
                                html += marked.parse(finalResult.reply);
                            } else {
                                html += `<pre>${finalResult.reply}</pre>`;
                            }
                            
                            html += `</div>`;
                            contentDiv.innerHTML = html;
                            
                            // 更新会话 ID
                            if (finalResult.session_id && !currentSessionId) {
                                currentSessionId = finalResult.session_id;
                                await loadSessions();
                            }
                            
                            scrollToBottom();
                            break;
                            
                        case 'error':
                            contentDiv.textContent = `❌ 任务失败：${event.data.error}`;
                            break;
                    }
                } catch (e) {
                    console.error('解析 SSE 数据失败:', e);
                }
            }
        }
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

// 跳转到产业链Tab
function jumpToIndustryTab(industryName) {
    console.log('跳转到产业链:', industryName);
    
    // 切换到产业链Tab
    switchSidebarTab('industry');
    
    // 自动填充搜索框并搜索
    setTimeout(() => {
        const searchInput = document.getElementById('industrySearchInput');
        if (searchInput) {
            searchInput.value = industryName;
            searchIndustry();
        }
    }, 100);
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
        
        // 尝试渲染产业链图谱
        setTimeout(() => {
            renderGraphInMessage(contentDiv, content);
            
            // 检测是否包含产业链信息，显示跳转提示
            const industryMatch = content.match(/(氢能|核能|新能源|储能|半导体|光伏|风电|锂电池|燃料电池|钢铁|化工|有色金属|稀土|生物医药|航空航天|新材料|5G|物联网|大数据|人工智能|医疗器械|中医药|疫苗)/);
            if (industryMatch && !content.includes('GRAPH_DATA_START')) {
                // 如果提到了产业链但没有图谱，显示跳转提示
                const tipDiv = document.createElement('div');
                tipDiv.className = 'industry-jump-tip';
                tipDiv.innerHTML = `

                    💡 检测到产业链关键词，点击 <a href="javascript:void(0)" onclick="jumpToIndustryTab('${industryMatch[1]}')">查看完整可视化图谱 →</a>
                `;
                contentDiv.appendChild(tipDiv);
            }
        }, 100);
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

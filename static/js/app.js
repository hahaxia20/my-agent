/* ========================================
   My Agent - 主应用入口
   ======================================== */

// 页面加载时的初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 1. 检查登录状态
    if (!checkAuth()) {
        return;
    }

    // 2. 检查 marked 是否加载
    if (typeof marked === 'undefined') {
        console.error('❌ marked 库未加载！');
    } else {
        console.log('✅ marked 库已加载');
    }

    // 3. 初始化欢迎文本
    updateWelcomeText(currentMode);
    
    // 4. 显示当前用户
    displayCurrentUser();

    // 5. 加载会话列表
    await loadSessions();

    // 6. 聚焦输入框
    document.getElementById('messageInput').focus();

    console.log('✅ My Agent 初始化完成');
});

// 页面关闭时的清理
window.addEventListener('beforeunload', () => {
    // 无特殊清理需要
});

// 全局错误处理
window.addEventListener('error', (e) => {
    console.error('全局错误:', e.error);
});

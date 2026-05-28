/* ========================================
   My Agent - 登录页面逻辑
   ======================================== */

const API_BASE_URL = 'http://localhost:8001';

// 切换标签
function switchTab(tab) {
    const tabs = document.querySelectorAll('.auth-tab');
    const forms = document.querySelectorAll('.auth-form');

    tabs.forEach(t => t.classList.remove('active'));
    forms.forEach(f => f.classList.remove('active'));

    if (tab === 'login') {
        tabs[0].classList.add('active');
        document.getElementById('loginForm').classList.add('active');
    } else {
        tabs[1].classList.add('active');
        document.getElementById('registerForm').classList.add('active');
    }

    // 清除错误信息
    hideMessages();
}

// 隐藏所有消息
function hideMessages() {
    document.querySelectorAll('.error-message, .success-message').forEach(el => {
        el.classList.remove('show');
    });
}

// 显示错误
function showError(elementId, message) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.classList.add('show');
}

// 显示成功
function showSuccess(elementId, message) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.classList.add('show');
}

// 处理登录
async function handleLogin() {
    hideMessages();

    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;

    if (!username) {
        showError('loginError', '请输入用户名');
        return;
    }

    if (!password) {
        showError('loginError', '请输入密码');
        return;
    }

    const btn = document.getElementById('loginBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span>登录中...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            // 保存 token 和用户信息
            localStorage.setItem('authToken', data.token);
            localStorage.setItem('currentUser', data.username);

            // 跳转到主界面
            window.location.href = 'index.html';
        } else {
            showError('loginError', data.detail || '登录失败');
        }
    } catch (error) {
        showError('loginError', '网络错误，请检查服务是否启动');
        console.error('登录错误:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = '登录';
    }
}

// 处理注册
async function handleRegister() {
    hideMessages();

    const username = document.getElementById('registerUsername').value.trim();
    const password = document.getElementById('registerPassword').value;
    const confirmPassword = document.getElementById('registerConfirmPassword').value;

    if (!username || username.length < 3) {
        showError('registerError', '用户名至少3个字符');
        return;
    }

    if (!password || password.length < 6) {
        showError('registerError', '密码至少6个字符');
        return;
    }

    if (password !== confirmPassword) {
        showError('registerError', '两次输入的密码不一致');
        return;
    }

    const btn = document.getElementById('registerBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span>注册中...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('registerSuccess', '注册成功！正在跳转到登录页...');

            // 2秒后跳转到登录页
            setTimeout(() => {
                // 清空表单
                document.getElementById('registerUsername').value = '';
                document.getElementById('registerPassword').value = '';
                document.getElementById('registerConfirmPassword').value = '';

                // 切换到登录 Tab
                switchTab('login');

                // 自动填充用户名
                document.getElementById('loginUsername').value = username;
                document.getElementById('loginPassword').focus();

                // 显示成功提示
                showError('loginError', '');  // 清除错误
                const loginSuccess = document.getElementById('loginError');
                loginSuccess.textContent = '✅ 注册成功！请登录';
                loginSuccess.style.background = '#efe';
                loginSuccess.style.color = '#3c3';
                loginSuccess.style.borderLeftColor = '#3c3';
                loginSuccess.classList.add('show');
            }, 1000);
        } else {
            showError('registerError', data.detail || '注册失败');
        }
    } catch (error) {
        showError('registerError', '网络错误，请检查服务是否启动');
        console.error('注册错误:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = '注册';
    }
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    // 检查是否已登录
    const token = localStorage.getItem('authToken');
    if (token) {
        // 已登录，直接跳转
        window.location.href = 'index.html';
        return;
    }

    // 回车键提交
    document.getElementById('loginPassword').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleLogin();
    });

    document.getElementById('registerConfirmPassword').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleRegister();
    });
});

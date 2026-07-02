/* ========================================
   My Agent - Login Page Logic
   ======================================== */

const API_BASE_URL = '';

function switchTab(tab) {
    const tabs = document.querySelectorAll('.auth-tab');
    const forms = document.querySelectorAll('.auth-form');

    tabs.forEach((item) => item.classList.remove('active'));
    forms.forEach((item) => item.classList.remove('active'));

    if (tab === 'login') {
        tabs[0].classList.add('active');
        document.getElementById('loginForm').classList.add('active');
    } else {
        tabs[1].classList.add('active');
        document.getElementById('registerForm').classList.add('active');
    }

    hideMessages();
}

function hideMessages() {
    document.querySelectorAll('.error-message, .success-message').forEach((element) => {
        element.classList.remove('show');
        element.textContent = '';
    });
}

function showError(elementId, message) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.classList.add('show');
}

function showSuccess(elementId, message) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.classList.add('show');
}

async function handleLogin() {
    hideMessages();

    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;

    if (!username) {
        showError('loginError', 'Please enter a username');
        return;
    }

    if (!password) {
        showError('loginError', 'Please enter a password');
        return;
    }

    const btn = document.getElementById('loginBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span>Signing in...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            localStorage.setItem('authToken', data.token);
            localStorage.setItem('currentUser', data.username);
            window.location.href = 'index.html';
        } else {
            showError('loginError', data.detail || 'Login failed');
        }
    } catch (error) {
        showError('loginError', 'Network error. Check whether the service is running.');
        console.error('Login error:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Login';
    }
}

async function handleRegister() {
    hideMessages();

    const username = document.getElementById('registerUsername').value.trim();
    const password = document.getElementById('registerPassword').value;
    const confirmPassword = document.getElementById('registerConfirmPassword').value;

    if (!username || username.length < 3) {
        showError('registerError', 'Username must be at least 3 characters');
        return;
    }

    if (!password || password.length < 6) {
        showError('registerError', 'Password must be at least 6 characters');
        return;
    }

    if (password !== confirmPassword) {
        showError('registerError', 'Passwords do not match');
        return;
    }

    const btn = document.getElementById('registerBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span>Creating account...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('registerSuccess', 'Registration successful. Redirecting to login...');

            setTimeout(() => {
                document.getElementById('registerUsername').value = '';
                document.getElementById('registerPassword').value = '';
                document.getElementById('registerConfirmPassword').value = '';

                switchTab('login');
                document.getElementById('loginUsername').value = username;
                document.getElementById('loginPassword').focus();
                showSuccess('loginSuccess', 'Registration successful. Please sign in.');
            }, 1000);
        } else {
            showError('registerError', data.detail || 'Registration failed');
        }
    } catch (error) {
        showError('registerError', 'Network error. Check whether the service is running.');
        console.error('Registration error:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Register';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('authToken');
    if (token) {
        window.location.href = 'index.html';
        return;
    }

    document.getElementById('loginPassword').addEventListener('keypress', (event) => {
        if (event.key === 'Enter') handleLogin();
    });

    document.getElementById('registerConfirmPassword').addEventListener('keypress', (event) => {
        if (event.key === 'Enter') handleRegister();
    });
});

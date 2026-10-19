// static/js/main.js

// Таймер сессии
class SessionTimer {
    constructor(timeoutMinutes = 15) {
        this.timeoutMinutes = timeoutMinutes;
        this.timeLeft = timeoutMinutes * 60;
        this.timerInterval = null;
        this.events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
        this.init();
    }

    init() {
        this.startTimer();
        this.setupEventListeners();
    }

    startTimer() {
        this.updateDisplay();

        this.timerInterval = setInterval(() => {
            this.timeLeft--;
            this.updateDisplay();

            if (this.timeLeft <= 0) {
                this.showTimeoutWarning();
                clearInterval(this.timerInterval);
            }

            // Предупреждение за 2 минуты
            if (this.timeLeft === 120) {
                this.showWarning();
            }
        }, 1000);
    }

    resetTimer() {
        this.timeLeft = this.timeoutMinutes * 60;
        this.updateDisplay();

        // Обновление активности на сервере
        fetch('/update_activity', { method: 'POST' }).catch(() => {});
    }

    setupEventListeners() {
        this.events.forEach(event => {
            document.addEventListener(event, () => this.resetTimer(), { passive: true });
        });
    }

    updateDisplay() {
        const minutes = Math.floor(this.timeLeft / 60);
        const seconds = this.timeLeft % 60;
        const display = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

        const timerElement = document.getElementById('timer-countdown');
        if (timerElement) {
            timerElement.textContent = display;

            // Цветовое предупреждение
            if (this.timeLeft < 120) {
                timerElement.style.color = '#dc3545';
                timerElement.style.fontWeight = 'bold';
            } else if (this.timeLeft < 300) {
                timerElement.style.color = '#ffc107';
            } else {
                timerElement.style.color = '#e0e0e0';
                timerElement.style.fontWeight = 'normal';
            }
        }
    }

    showWarning() {
        const toast = document.createElement('div');
        toast.className = 'toast toast-warning';
        toast.innerHTML = `
            <span>⚠️</span>
            <span>Сессия истекает через 2 минуты. Выполните любое действие для продления.</span>
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 5000);
    }

    showTimeoutWarning() {
        const toast = document.createElement('div');
        toast.className = 'toast toast-error';
        toast.innerHTML = `
            <span>⏰</span>
            <span>Время сессии истекло. Вы будете перенаправлены на страницу входа.</span>
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            window.location.href = '/logout';
        }, 3000);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Запуск таймера только для авторизованных пользователей
    if (document.getElementById('timer-countdown')) {
        new SessionTimer(15);
    }

    // Инициализация модальных окон
    initializeModals();

    // Закрытие flash-сообщений
    initializeFlashMessages();
});

// Функции для модальных окон
function initializeModals() {
    const modals = document.querySelectorAll('.modal');

    modals.forEach(modal => {
        // Закрытие по клику вне модального окна
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal(modal);
            }
        });

        // Закрытие по Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.style.display === 'flex') {
                closeModal(modal);
            }
        });
    });
}

function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('show');
    }
}

function closeModal(modal) {
    modal.style.display = 'none';
    modal.classList.remove('show');
}

// Автоматическое закрытие flash-сообщений
function initializeFlashMessages() {
    const alerts = document.querySelectorAll('.alert');

    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.5s ease';
            setTimeout(() => {
                alert.remove();
            }, 500);
        }, 5000);
    });
}

// Вспомогательные функции
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const options = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    };
    return date.toLocaleDateString('ru-RU', options);
}

// API запросы
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || 'Ошибка запроса');
        }

        return result;
    } catch (error) {
        console.error('API Error:', error);
        showNotification(error.message, 'error');
        throw error;
    }
}

// Уведомления (toast)
function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
        'info': 'ℹ️',
        'success': '✅',
        'warning': '⚠️',
        'error': '❌'
    };

    toast.innerHTML = `
        <span>${icons[type] || '📢'}</span>
        <span>${message}</span>
    `;

    document.body.appendChild(toast);

    // Анимация появления
    setTimeout(() => toast.classList.add('show'), 100);

    // Автоматическое скрытие
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Добавляем стили для toast уведомлений
const toastStyles = document.createElement('style');
toastStyles.textContent = `
    .toast {
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        gap: 10px;
        color: white;
        z-index: 9999;
        opacity: 0;
        transform: translateY(20px);
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .toast.show {
        opacity: 1;
        transform: translateY(0);
    }

    .toast-info { background-color: #17a2b8; }
    .toast-success { background-color: #28a745; }
    .toast-warning { background-color: #ffc107; color: #000; }
    .toast-error { background-color: #dc3545; }

    @media (max-width: 768px) {
        .toast {
            left: 20px;
            right: 20px;
            bottom: 10px;
        }
    }
`;
document.head.appendChild(toastStyles);
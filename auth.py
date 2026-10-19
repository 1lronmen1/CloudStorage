# auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)


# Импортируем db из models, но не здесь, чтобы избежать циклического импорта
# Вместо этого будем получать доступ к db через current_app

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Получаем db из конфигурации приложения
        from flask import current_app
        db = current_app.config['database']

        conn = db.get_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND is_active = 1',
                            (username,)).fetchone()
        conn.close()

        if user and db.verify_password(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            session['last_activity'] = datetime.now().isoformat()
            session.permanent = True

            # Обновление времени последнего входа
            conn = db.get_connection()
            conn.execute('UPDATE users SET last_login = ? WHERE id = ?',
                         (datetime.now(), user['id']))
            conn.commit()
            conn.close()

            flash('Вход выполнен успешно', 'success')
            return redirect(url_for('upload'))

        flash('Неверное имя пользователя или пароль', 'error')
        return render_template('login.html')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # Здесь должна быть логика восстановления пароля
        flash('Инструкции по восстановлению пароля отправлены на email', 'info')
        return redirect(url_for('auth.login'))
    return render_template('forgot_password.html')
# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
from config import Config
from models import Database
from auth import auth_bp
import os
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)

# Загружаем конфигурацию
app.config.from_object(Config)

# Важные настройки
app.secret_key = Config.SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

# Инициализация базы данных
db = Database()
db.init_db()

# Сохраняем db в конфигурации приложения
app.config['database'] = db

# Регистрация blueprint для аутентификации
app.register_blueprint(auth_bp)


# Декоратор для проверки аутентификации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('auth.login'))
        if not session.get('is_admin'):
            flash('Доступ запрещен. Требуются права администратора.', 'error')
            return redirect(url_for('upload'))
        return f(*args, **kwargs)

    return decorated_function


# Проверка активности сессии перед каждым запросом
@app.before_request
def check_session_timeout():
    if 'user_id' in session and request.endpoint not in ['auth.login', 'static', 'update_activity']:
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                last_activity = datetime.fromisoformat(last_activity)
                if datetime.now() - last_activity > timedelta(minutes=15):
                    # Логирование автовыхода
                    conn = db.get_connection()
                    conn.execute('''
                        INSERT INTO upload_logs (user_id, filename, file_size, file_type, destination_path, ip_address, user_agent)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (session['user_id'], 'AUTO_LOGOUT', 0, 'system', 'session_timeout', request.remote_addr,
                          request.headers.get('User-Agent', 'Unknown')))
                    conn.commit()
                    conn.close()

                    session.clear()
                    flash('Сессия истекла из-за неактивности (15 минут)', 'warning')
                    return redirect(url_for('auth.login'))
            except (ValueError, TypeError):
                pass
        session['last_activity'] = datetime.now().isoformat()


# Главная страница
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return redirect(url_for('upload'))


# Страница загрузки
@app.route('/upload')
@login_required
def upload():
    disk_info = db.check_disk_space()

    # Получаем список существующих каталогов в CLOUD_ROOT
    directories = ['NOSORT']  # Каталог по умолчанию всегда первый
    if os.path.exists(Config.CLOUD_ROOT):
        try:
            for item in os.listdir(Config.CLOUD_ROOT):
                item_path = os.path.join(Config.CLOUD_ROOT, item)
                if os.path.isdir(item_path) and item != 'NOSORT':
                    directories.append(item)
        except Exception as e:
            print(f"Ошибка чтения каталогов: {e}")

    return render_template('upload.html', disk_info=disk_info, directories=directories)


# API для получения информации о диске
@app.route('/get_disk_info')
@login_required
def get_disk_info():
    disk_info = db.check_disk_space()
    if disk_info:
        return jsonify({'success': True, 'data': disk_info})
    return jsonify({'success': False, 'message': 'Не удалось получить информацию о диске'})


# API для получения списка каталогов
@app.route('/get_directories')
@login_required
def get_directories():
    directories = ['NOSORT']
    if os.path.exists(Config.CLOUD_ROOT):
        try:
            for item in os.listdir(Config.CLOUD_ROOT):
                item_path = os.path.join(Config.CLOUD_ROOT, item)
                if os.path.isdir(item_path) and item != 'NOSORT':
                    directories.append(item)
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})

    return jsonify({'success': True, 'directories': directories})


# API для проверки каталога
@app.route('/check_directory', methods=['POST'])
@login_required
def check_directory():
    data = request.get_json()
    directory_name = data.get('directory', '').strip()

    if not directory_name:
        return jsonify({
            'success': False,
            'message': 'Введите имя каталога',
            'full_path': None,
            'exists': False
        })

    # Очистка имени каталога
    safe_name = "".join(c for c in directory_name if c.isalnum() or c in (' ', '-', '_', '.', '(', ')'))

    if safe_name != directory_name:
        return jsonify({
            'success': False,
            'message': 'Имя каталога содержит недопустимые символы',
            'full_path': None,
            'exists': False
        })

    full_path = os.path.join(Config.CLOUD_ROOT, safe_name)
    exists = os.path.exists(full_path)

    if not exists:
        return jsonify({
            'success': False,
            'message': f'Каталог "{safe_name}" не существует. Создать каталог F:\\CLOUD\\{safe_name}?',
            'full_path': full_path,
            'exists': False,
            'directory_name': safe_name
        })

    return jsonify({
        'success': True,
        'message': f'Каталог "{safe_name}" существует',
        'full_path': full_path,
        'exists': True,
        'directory_name': safe_name
    })


# API для создания каталога
@app.route('/create_directory', methods=['POST'])
@login_required
def create_directory():
    data = request.get_json()
    full_path = data.get('full_path', '')

    # Проверка что путь внутри CLOUD_ROOT
    if not full_path.startswith(Config.CLOUD_ROOT):
        return jsonify({'success': False, 'message': 'Недопустимый путь'})

    try:
        os.makedirs(full_path, exist_ok=True)

        # Логирование создания каталога
        db.log_action(
            user_id=session['user_id'],
            filename=f'CREATE_DIR: {full_path}',
            file_size=0,
            destination_path=full_path,
            file_type='directory',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', 'Unknown')
        )

        return jsonify({
            'success': True,
            'message': f'Каталог успешно создан: {full_path}',
            'directory_name': os.path.basename(full_path)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка создания каталога: {str(e)}'
        })


# Безопасное имя файла с поддержкой кириллицы
def safe_filename_cyrillic(filename):
    """
    Безопасное имя файла с поддержкой кириллицы и других не-ASCII символов.
    Заменяет только опасные символы, сохраняя буквы всех алфавитов.
    """
    # Сохраняем расширение
    name, ext = os.path.splitext(filename)

    # Заменяем опасные символы, но сохраняем буквы (включая кириллицу), цифры, пробелы, дефисы, подчеркивания и точки
    dangerous_chars = '\\/:*?"<>|'
    safe_name = ''.join(c if c not in dangerous_chars else '_' for c in name)

    # Убираем точки в начале и конце имени (Windows не любит)
    safe_name = safe_name.strip('. ')

    # Если имя пустое после очистки, используем "file"
    if not safe_name:
        safe_name = 'file'

    return safe_name + ext


# API для загрузки файлов (СОХРАНЯЕТ ИСХОДНЫЕ ИМЕНА С КИРИЛЛИЦЕЙ)
@app.route('/upload_files', methods=['POST'])
@login_required
def upload_files():
    if 'files[]' not in request.files:
        return jsonify({'success': False, 'message': 'Файлы не выбраны'})

    files = request.files.getlist('files[]')
    if not files or files[0].filename == '':
        return jsonify({'success': False, 'message': 'Файлы не выбраны'})

    directory = request.form.get('directory', 'NOSORT')

    # Определение полного пути
    if directory.startswith(Config.CLOUD_ROOT):
        target_dir = directory
    else:
        target_dir = os.path.join(Config.CLOUD_ROOT, directory)

    # Проверка существования каталога
    if not os.path.exists(target_dir):
        return jsonify({
            'success': False,
            'message': f'Каталог {directory} не существует',
            'directory_not_exists': True,
            'directory': directory
        })

    # Проверка свободного места
    total_size = 0
    file_info_list = []

    for file in files:
        if file.filename == '':
            continue
        file.seek(0, 2)
        size = file.tell()
        total_size += size
        file.seek(0)
        file_info_list.append({'file': file, 'size': size, 'filename': file.filename})

    disk_info = db.check_disk_space()
    if disk_info and total_size > disk_info['free_gb'] * 1024 ** 3:
        return jsonify({
            'success': False,
            'message': f'Недостаточно свободного места. Свободно: {disk_info["free_gb"]} GB, требуется: {total_size / (1024 ** 3):.2f} GB'
        })

    uploaded_files = []
    failed_files = []

    for file_info in file_info_list:
        file = file_info['file']
        original_filename = file.filename

        try:
            # Используем безопасное имя с поддержкой кириллицы
            safe_filename = safe_filename_cyrillic(original_filename)

            # Если файл с таким именем существует, добавляем номер
            file_path = os.path.join(target_dir, safe_filename)

            if os.path.exists(file_path):
                name, ext = os.path.splitext(safe_filename)
                counter = 1
                while os.path.exists(file_path):
                    new_name = f"{name} ({counter}){ext}"
                    file_path = os.path.join(target_dir, new_name)
                    counter += 1

            # Сохраняем файл
            file.save(file_path)
            file_size = os.path.getsize(file_path)

            # Определяем тип файла
            ext = os.path.splitext(original_filename)[1]
            file_type = ext[1:].lower() if ext else 'unknown'

            # Логирование загрузки
            db.log_action(
                user_id=session['user_id'],
                filename=os.path.basename(file_path),
                file_size=file_size,
                destination_path=target_dir,
                file_type=file_type,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', 'Unknown')
            )

            uploaded_files.append({
                'name': original_filename,
                'saved_name': os.path.basename(file_path),
                'size': file_size,
                'size_formatted': format_size(file_size),
                'path': file_path
            })

        except Exception as e:
            failed_files.append({
                'name': original_filename,
                'error': str(e)
            })

    return jsonify({
        'success': len(uploaded_files) > 0,
        'uploaded': uploaded_files,
        'failed': failed_files,
        'total_uploaded': len(uploaded_files),
        'total_failed': len(failed_files),
        'total_size_formatted': format_size(sum(f['size'] for f in uploaded_files))
    })


# Страница журнала
@app.route('/logs')
@login_required
def logs():
    page = request.args.get('page', 1, type=int)
    per_page = 50

    logs_data, total = db.get_logs(page, per_page)

    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    return render_template('logs.html',
                           logs=logs_data,
                           page=page,
                           total_pages=total_pages,
                           total_records=total)


# API для поиска в логах
@app.route('/api/logs/search', methods=['POST'])
@login_required
def search_logs():
    data = request.get_json()
    query = data.get('query', '')

    logs_data = db.search_logs(query)

    return jsonify({
        'success': True,
        'logs': [dict(row) for row in logs_data]
    })


# API для очистки логов (только для админа)
@app.route('/api/logs/clear', methods=['POST'])
@login_required
@admin_required
def clear_logs():
    conn = db.get_connection()
    conn.execute('DELETE FROM upload_logs')
    conn.commit()
    conn.close()

    # Логируем очистку
    db.log_action(
        user_id=session['user_id'],
        filename='CLEAR_LOGS',
        file_size=0,
        destination_path='system',
        file_type='system',
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', 'Unknown')
    )

    return jsonify({'success': True, 'message': 'Логи очищены'})


# API для создания пользователя (POST)
@app.route('/api/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'message': 'Нет данных'})

        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        is_admin = data.get('is_admin', False)

        print(f"Создание пользователя: username={username}, email={email}, is_admin={is_admin}")

        if not all([username, email, password]):
            return jsonify({'success': False, 'message': 'Заполните все поля'})

        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Пароль должен быть не менее 6 символов'})

        success, message = db.create_user(username, email, password, is_admin)

        if success:
            db.log_action(
                user_id=session['user_id'],
                filename=f'CREATE_USER: {username}',
                file_size=0,
                destination_path='system',
                file_type='user_management',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', 'Unknown')
            )

        return jsonify({'success': success, 'message': message})

    except Exception as e:
        print(f"Ошибка создания пользователя: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Ошибка сервера: {str(e)}'})


# API для работы с конкретным пользователем (GET, PUT, DELETE)
@app.route('/api/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@admin_required
def manage_user(user_id):
    # GET - получить пользователя
    if request.method == 'GET':
        try:
            conn = db.get_connection()
            user = conn.execute('''
                SELECT id, username, email, is_admin, is_active, 
                       created_at, last_login 
                FROM users 
                WHERE id = ?
            ''', (user_id,)).fetchone()
            conn.close()

            if user:
                return jsonify({
                    'success': True,
                    'user': {
                        'id': user['id'],
                        'username': user['username'],
                        'email': user['email'],
                        'is_admin': bool(user['is_admin']),
                        'is_active': bool(user['is_active']),
                        'created_at': str(user['created_at']) if user['created_at'] else None,
                        'last_login': str(user['last_login']) if user['last_login'] else None
                    }
                })

            return jsonify({'success': False, 'message': 'Пользователь не найден'})

        except Exception as e:
            print(f"Ошибка получения пользователя {user_id}: {str(e)}")
            return jsonify({'success': False, 'message': f'Ошибка сервера: {str(e)}'})

    # PUT - обновить пользователя
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            is_admin = data.get('is_admin', False)
            is_active = data.get('is_active', True)

            if not all([username, email]):
                return jsonify({'success': False, 'message': 'Имя пользователя и email обязательны'})

            if password and len(password) < 6:
                return jsonify({'success': False, 'message': 'Пароль должен быть не менее 6 символов'})

            conn = db.get_connection()

            # Проверка уникальности username и email
            existing = conn.execute('''
                SELECT id FROM users 
                WHERE (username = ? OR email = ?) AND id != ?
            ''', (username, email, user_id)).fetchone()

            if existing:
                conn.close()
                return jsonify({'success': False, 'message': 'Пользователь с таким именем или email уже существует'})

            # Обновление пользователя
            if password:
                password_hash = db.hash_password(password)
                conn.execute('''
                    UPDATE users 
                    SET username = ?, email = ?, password_hash = ?, is_admin = ?, is_active = ?
                    WHERE id = ?
                ''', (username, email, password_hash, is_admin, is_active, user_id))
            else:
                conn.execute('''
                    UPDATE users 
                    SET username = ?, email = ?, is_admin = ?, is_active = ?
                    WHERE id = ?
                ''', (username, email, is_admin, is_active, user_id))

            conn.commit()

            # Логирование
            db.log_action(
                user_id=session['user_id'],
                filename=f'UPDATE_USER: {username} (ID={user_id})',
                file_size=0,
                destination_path='system',
                file_type='user_management',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', 'Unknown')
            )

            conn.close()
            return jsonify({'success': True, 'message': f'Пользователь "{username}" обновлен'})

        except Exception as e:
            print(f"Ошибка обновления пользователя {user_id}: {str(e)}")
            return jsonify({'success': False, 'message': f'Ошибка обновления: {str(e)}'})

    # DELETE - удалить пользователя
    elif request.method == 'DELETE':
        try:
            if user_id == session['user_id']:
                return jsonify({'success': False, 'message': 'Нельзя удалить самого себя'})

            if user_id == 1:  # Главный админ
                return jsonify({'success': False, 'message': 'Нельзя удалить главного администратора'})

            conn = db.get_connection()
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()

            # Логирование удаления пользователя
            db.log_action(
                user_id=session['user_id'],
                filename=f'DELETE_USER: ID={user_id}',
                file_size=0,
                destination_path='system',
                file_type='user_management',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', 'Unknown')
            )

            conn.close()
            return jsonify({'success': True, 'message': f'Пользователь ID={user_id} удален'})

        except Exception as e:
            print(f"Ошибка удаления пользователя {user_id}: {str(e)}")
            return jsonify({'success': False, 'message': f'Ошибка удаления: {str(e)}'})


# Панель администратора
@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    users = db.get_all_users()
    return render_template('admin.html', users=users)


# API для обновления активности сессии
@app.route('/update_activity', methods=['POST'])
@login_required
def update_activity():
    session['last_activity'] = datetime.now().isoformat()
    return jsonify({'success': True})


# API для смены пароля текущим пользователем
@app.route('/api/change_password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Заполните все поля'})

    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'Новый пароль должен быть не менее 6 символов'})

    conn = db.get_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    if not user or not db.verify_password(user['password_hash'], current_password):
        conn.close()
        return jsonify({'success': False, 'message': 'Неверный текущий пароль'})

    # Обновление пароля
    new_password_hash = db.hash_password(new_password)
    conn.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                 (new_password_hash, session['user_id']))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Пароль успешно изменен'})


# API для восстановления пароля
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        conn = db.get_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user:
            # Здесь должна быть отправка email
            flash('Инструкции по восстановлению пароля отправлены на указанный email', 'info')
        else:
            flash('Если указанный email зарегистрирован, инструкции отправлены', 'info')

        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


# Фильтр для форматирования размера файла
@app.template_filter('file_size_format')
def file_size_format(size_bytes):
    if not size_bytes:
        return '0 B'
    return format_size(size_bytes)



# Вспомогательные функции
def format_size(size_bytes):
    if size_bytes == 0:
        return '0 B'
    size_bytes = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


if __name__ == '__main__':
    # Создаем необходимые каталоги
    os.makedirs(Config.CLOUD_ROOT, exist_ok=True)
    os.makedirs(Config.DEFAULT_UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.LOGS_DIR, exist_ok=True)
    os.makedirs(Config.TEMP_DIR, exist_ok=True)

    # Создаем SSL контекст
    cert_path = Config.SSL_CERT
    key_path = Config.SSL_KEY

    if os.path.exists(cert_path) and os.path.exists(key_path):
        ssl_context = (cert_path, key_path)
        print("✓ SSL сертификаты найдены")
    else:
        ssl_context = 'adhoc'
        print("⚠ SSL сертификаты не найдены, используется временный сертификат")

    print(f"✓ Сервер запущен на https://0.0.0.0:{Config.PORT}")
    print(f"✓ Локальный доступ: https://localhost:{Config.PORT}")
    print(f"✓ Корневой каталог хранения: {Config.CLOUD_ROOT}")
    print(f"✓ Каталог по умолчанию: {Config.DEFAULT_UPLOAD_FOLDER}")
    print(f"✓ Логин по умолчанию: admin / admin123")

    app.run(
        host=Config.HOST,
        port=Config.PORT,
        ssl_context=ssl_context,
        debug=False
    )
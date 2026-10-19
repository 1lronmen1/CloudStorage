# models.py
import sqlite3
import hashlib
import os
import secrets
from datetime import datetime
from config import Config


class Database:
    def __init__(self):
        self.db_path = Config.DATABASE_PATH
        # Проверка и создание директории для БД
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()

        # Создание таблиц
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS upload_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                file_size INTEGER,
                file_type TEXT,
                destination_path TEXT NOT NULL,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        ''')

        # Создание администратора по умолчанию
        admin_password = self.hash_password('admin123')
        try:
            conn.execute('''
                INSERT OR IGNORE INTO users (username, email, password_hash, is_admin)
                VALUES (?, ?, ?, 1)
            ''', ('admin', 'admin@localhost', admin_password))
            conn.commit()
        except Exception as e:
            print(f"Ошибка создания админа: {e}")

        conn.close()
        print(f"[OK] База данных инициализирована: {self.db_path}")

    @staticmethod
    def hash_password(password):
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                  salt.encode('utf-8'), 100000)
        return salt + ':' + key.hex()

    @staticmethod
    def verify_password(stored_password, provided_password):
        try:
            salt, key_hex = stored_password.split(':')
            stored_key = bytes.fromhex(key_hex)
            new_key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'),
                                          salt.encode('utf-8'), 100000)
            return new_key == stored_key
        except Exception:
            return False

    def check_disk_space(self):
        """Проверка свободного места на диске F:\\"""
        try:
            import shutil
            # Проверяем диск, на котором находится CLOUD_ROOT
            drive = os.path.splitdrive(Config.CLOUD_ROOT)[0] + '\\'
            total, used, free = shutil.disk_usage(drive)
            return {
                'drive': drive,
                'total_gb': round(total / (1024 ** 3), 2),
                'used_gb': round(used / (1024 ** 3), 2),
                'free_gb': round(free / (1024 ** 3), 2),
                'percent_used': round((used / total) * 100, 1),
                'percent_free': round((free / total) * 100, 1)
            }
        except Exception as e:
            print(f"Ошибка проверки диска: {e}")
            return None

    def get_user_by_id(self, user_id):
        conn = self.get_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return user

    def log_action(self, user_id, filename=None, file_size=None, destination_path=None,
                   file_type=None, ip_address=None, user_agent=None):
        conn = self.get_connection()
        conn.execute('''
            INSERT INTO upload_logs 
            (user_id, filename, file_size, file_type, destination_path, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, filename, file_size, file_type, destination_path, ip_address, user_agent))
        conn.commit()
        conn.close()

    def get_logs(self, page=1, per_page=50):
        conn = self.get_connection()
        total = conn.execute('SELECT COUNT(*) FROM upload_logs').fetchone()[0]
        logs = conn.execute('''
            SELECT l.*, u.username 
            FROM upload_logs l 
            JOIN users u ON l.user_id = u.id 
            ORDER BY l.upload_time DESC 
            LIMIT ? OFFSET ?
        ''', (per_page, (page - 1) * per_page)).fetchall()
        conn.close()
        return logs, total

    def search_logs(self, query):
        conn = self.get_connection()
        logs = conn.execute('''
            SELECT l.*, u.username 
            FROM upload_logs l 
            JOIN users u ON l.user_id = u.id 
            WHERE l.filename LIKE ? OR u.username LIKE ? OR l.destination_path LIKE ?
            ORDER BY l.upload_time DESC 
            LIMIT 100
        ''', (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
        conn.close()
        return logs

    def get_all_users(self):
        conn = self.get_connection()
        users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
        conn.close()
        return users

    def create_user(self, username, email, password, is_admin=False):
        """Создание нового пользователя"""
        conn = self.get_connection()
        try:
            password_hash = self.hash_password(password)
            conn.execute('''
                INSERT INTO users (username, email, password_hash, is_admin, is_active)
                VALUES (?, ?, ?, ?, 1)
            ''', (username, email, password_hash, is_admin))
            conn.commit()
            return True, f"Пользователь '{username}' успешно создан"
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                return False, f"Пользователь с именем '{username}' уже существует"
            elif 'email' in str(e):
                return False, f"Пользователь с email '{email}' уже существует"
            else:
                return False, f"Ошибка базы данных: {str(e)}"
        except Exception as e:
            print(f"Ошибка создания пользователя в БД: {e}")
            return False, f"Ошибка: {str(e)}"
        finally:
            conn.close()

    def delete_user(self, user_id):
        if user_id == 1:  # Нельзя удалить главного админа
            return False, "Нельзя удалить главного администратора"
        conn = self.get_connection()
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, "Пользователь удален"

    def get_system_logs(self, page=1, per_page=50):
        """Получение системных логов (создание каталогов, управление пользователями и т.д.)"""
        conn = self.get_connection()
        total = conn.execute('''
            SELECT COUNT(*) FROM upload_logs 
            WHERE file_type IN ('directory', 'system', 'user_management')
        ''').fetchone()[0]

        logs = conn.execute('''
            SELECT l.*, u.username 
            FROM upload_logs l 
            JOIN users u ON l.user_id = u.id 
            WHERE l.file_type IN ('directory', 'system', 'user_management')
            ORDER BY l.upload_time DESC 
            LIMIT ? OFFSET ?
        ''', (per_page, (page - 1) * per_page)).fetchall()

        conn.close()
        return logs, total

    def get_user_upload_stats(self, user_id=None):
        """Получение статистики загрузок"""
        conn = self.get_connection()

        if user_id:
            stats = conn.execute('''
                SELECT 
                    COUNT(*) as total_uploads,
                    SUM(file_size) as total_size,
                    COUNT(DISTINCT DATE(upload_time)) as active_days,
                    MAX(upload_time) as last_upload
                FROM upload_logs 
                WHERE user_id = ? AND file_type NOT IN ('directory', 'system', 'user_management')
            ''', (user_id,)).fetchone()
        else:
            stats = conn.execute('''
                SELECT 
                    COUNT(*) as total_uploads,
                    SUM(file_size) as total_size,
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(DISTINCT DATE(upload_time)) as active_days
                FROM upload_logs 
                WHERE file_type NOT IN ('directory', 'system', 'user_management')
            ''').fetchone()

        conn.close()
        return dict(stats) if stats else {}
# config.py
import os
from datetime import timedelta


class Config:
    # Секретный ключ
    SECRET_KEY = os.urandom(24)

    # Пути к базе данных и проекту
#    BASE_DIR = r'C:\Users\admsys\PycharmProjects\CloudStorage'
    # Автоматически определяем папку, где лежит config.py
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'cloud_storage.db')

    # Настройки хранилища
    CLOUD_ROOT = r'c:\CLOUD'
    DEFAULT_UPLOAD_FOLDER = os.path.join(CLOUD_ROOT, 'NOSORT')

    # Директории проекта
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')
    TEMP_DIR = os.path.join(BASE_DIR, 'uploads')

    # Настройки сессии
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)
    SESSION_TIMEOUT = 15  # минут

    # Настройки загрузки файлов
    MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB максимум
    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx',
        'xls', 'xlsx', 'ppt', 'pptx', 'mp4', 'avi', 'mov', 'zip',
        'rar', '7z', 'mp3', 'wav', 'flac', 'heic', 'heif', 'webp',
        'svg', 'bmp', 'tiff', 'csv', 'json', 'xml', 'html', 'css',
        'js', 'py', 'sql', 'db', 'sqlite', 'iso', 'dmg', 'apk', 'ipa'
    }

    # SSL настройки
    SSL_CERT = os.path.join(BASE_DIR, 'certs', 'cert.pem')
    SSL_KEY = os.path.join(BASE_DIR, 'certs', 'key.pem')

    # Настройки хоста и порта
    HOST = '0.0.0.0'  # Слушать все интерфейсы
    PORT = 443  # HTTPS порт

    # Настройки почты для восстановления пароля (опционально)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # Дополнительные настройки Flask
    SESSION_COOKIE_SECURE = True  # Только HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Настройки безопасности
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.urandom(32)
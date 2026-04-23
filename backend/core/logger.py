import logging
from logging.handlers import RotatingFileHandler

# Создаем логгер
def setup_logger(
    name, log_file='app.log', level=logging.DEBUG,
    max_bytes=5*1024*1024,  # 5MB
    backup_count=3, format_string=None
) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    
    logger.setLevel(level)

    # Форматтер
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'

    formatter = logging.Formatter(format_string)
    
    # Хендлер для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_file = '.logs/' + log_file

    # Хендлер для записи в файл (опционально)
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=max_bytes, 
        backupCount=backup_count,
        encoding='utf-8'  # Важно для русских символов
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
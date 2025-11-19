import bcrypt

def hash_password(password: str) -> str:
    """Хэширование пароля с помощью bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')
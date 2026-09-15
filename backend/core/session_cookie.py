from fastapi import Response

from settings import config


_REFRESH_COOKIE_PATH = "/"


def set_refresh_cookie(response: Response, token: str) -> None:
    """Set the HttpOnly refresh cookie using the production security policy."""
    response.set_cookie(
        key=config.REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        max_age=config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=_REFRESH_COOKIE_PATH,
        domain=config.COOKIE_DOMAIN,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh cookie using exactly the same scope used to set it."""
    response.delete_cookie(
        key=config.REFRESH_COOKIE_NAME,
        path=_REFRESH_COOKIE_PATH,
        domain=config.COOKIE_DOMAIN,
        secure=config.COOKIE_SECURE,
        httponly=True,
        samesite=config.COOKIE_SAMESITE,
    )

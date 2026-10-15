"""Password hashing (PBKDF2-SHA256) and signed session tokens - standard library only."""
import base64
import hashlib
import hmac
import os
import time

from app.config import settings


def hash_password(password, iterations=None):
    iterations = iterations or settings.PASSWORD_ITERATIONS
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (iterations, salt.hex(), digest.hex())


def verify_password(password, stored):
    try:
        _algo, iterations, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False


def _sign(body):
    return hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()


def create_token(user_id):
    expires = int(time.time()) + settings.SESSION_HOURS * 3600
    body = base64.urlsafe_b64encode(("%d:%d" % (user_id, expires)).encode()).decode().rstrip("=")
    return body + "." + _sign(body)


def read_token(token):
    """Returns the user id inside a valid, unexpired token, otherwise None."""
    try:
        body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(body)):
            return None
        user_id, expires = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode().split(":")
        return int(user_id) if int(expires) >= time.time() else None
    except Exception:
        return None

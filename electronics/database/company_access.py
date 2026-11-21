import hashlib
from hmac import compare_digest
import secrets
import time

ITERATIONS = 240_000


def configured(db, slug):
    return db.execute("SELECT 1 FROM company_passwords WHERE slug=?", (slug,)).fetchone() is not None


def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


def exchange_password(db, slug, password, *, setup=False):
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        return 400, {"error":"Kata sandi harus 8–128 karakter."}
    now = int(time.time())
    existing = db.execute("SELECT salt,digest,failures,retry_after FROM company_passwords WHERE slug=?", (slug,)).fetchone()
    if setup:
        if existing:
            return 409, {"error":"Kata sandi perusahaan sudah diatur."}
        salt = secrets.token_bytes(24)
        db.execute("INSERT INTO company_passwords(slug,salt,digest) VALUES (?,?,?)",
                   (slug,salt,password_digest(password,salt)))
    elif existing is None:
        return 401, {"error":"Atur kata sandi perusahaan terlebih dahulu."}
    else:
        salt, digest, failures, retry_after = existing
        if retry_after > now:
            return 429, {"error":"Terlalu banyak percobaan. Coba kembali dalam 60 detik."}
        if not compare_digest(password_digest(password,salt),digest):
            failures += 1
            db.execute("UPDATE company_passwords SET failures=?,retry_after=? WHERE slug=?",
                       (0 if failures>=5 else failures, now+60 if failures>=5 else 0, slug))
            return 401, {"error":"Kata sandi salah."}
        db.execute("UPDATE company_passwords SET failures=0,retry_after=0 WHERE slug=?", (slug,))
    token = secrets.token_urlsafe(32)
    db.execute("DELETE FROM company_sessions WHERE expires<=?", (now,))
    db.execute("INSERT INTO company_sessions VALUES (?,?,?)", (token_digest(token),slug,now+3600))
    return 200, {"token":token,"expires_in":3600}


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).digest()


def authorized(db, slug, authorization):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not 32 <= len(token) <= 128:
        return False
    return db.execute("SELECT 1 FROM company_sessions WHERE token_hash=? AND slug=? AND expires>?",
                      (token_digest(token),slug,int(time.time()))).fetchone() is not None


def revoke(db, slug, authorization):
    if authorized(db,slug,authorization):
        db.execute("DELETE FROM company_sessions WHERE token_hash=? AND slug=?",
                   (token_digest(authorization.partition(" ")[2]),slug))

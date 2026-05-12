import re
from passlib.context import CryptContext
pwd = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')
USERNAME_RE = re.compile(r'^[a-z0-9]+$')

def hash_password(p): return pwd.hash(p)
def verify_password(p,h): return pwd.verify(p,h)
def valid_username(u): return bool(USERNAME_RE.fullmatch(u))

import bcrypt
import passlib
from passlib.context import CryptContext

print(f"bcrypt version: {bcrypt.__version__}")
print(f"passlib version: {passlib.__version__}")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
try:
    hash = pwd_context.hash("test")
    print(f"Hash success: {hash}")
except Exception as e:
    print(f"Hash failed: {e}")

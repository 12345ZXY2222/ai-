from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import UserInDB

print("Testing security functions...")
try:
    pwd = "password123"
    hashed = get_password_hash(pwd)
    print(f"Hash: {hashed}")
    
    is_valid = verify_password(pwd, hashed)
    print(f"Verify: {is_valid}")
    
    token = create_access_token({"sub": "testuser"})
    print(f"Token: {token}")
    
    print("All tests passed!")
except Exception as e:
    print(f"Error: {e}")

from dotenv import load_dotenv
from pwdlib import PasswordHash
from .orm_module import User
from .exeption_module import CustomException
import jwt
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Form
import os

# ---- Configuration ----- #

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
ACCESS_TOKEN_EXPIRE_MINUTES = ACCESS_TOKEN_EXPIRE_HOURS * 60
SUPER_ADMIN_USERNAME = os.getenv("SUPER_ADMIN_USERNAME")
SUPER_ADMIN_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD")

PASSWORD_HASH = PasswordHash.recommended()


USER_NOT_FOUND_EXCEPTION = CustomException("Utilisateur non trouvé", status_code=404)
INVALID_PASSWORD_EXCEPTION = CustomException("Mot de passe invalide", status_code=401)
INVALID_TOKEN_EXCEPTION = CustomException("Token invalide", status_code=401)

# ---- classes ----- #

class Token(BaseModel):
    access_token: str
    token_type: str


class CustomOAuth2Form(OAuth2PasswordRequestForm):
    def __init__(
        self,
        email: str = Form(...),
        password: str = Form(...),
    ):
        super().__init__(username=email, password=password, scope="", client_id=None, client_secret=None)

# ---- Fonctions de sécurité ----- #

def verify_password(plain_password, hashed_password):
    # Vérifie si le mot de passe en clair correspond au mot de passe haché
    return PASSWORD_HASH.verify(plain_password, hashed_password)

def hash_password(plain_password):
    # Hache le mot de passe en clair pour le stocker dans la base de données
    return PASSWORD_HASH.hash(plain_password)

def authenticate_user(db, email: str, password: str) -> User :
    # Authentifie un utilisateur en vérifiant son email et son mot de passe
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise USER_NOT_FOUND_EXCEPTION
    if not verify_password(password, user.password_hash):
        raise INVALID_PASSWORD_EXCEPTION
    return user

def authenticate_admin(db, email: str, password: str) -> bool :
    # Authentifie un administrateur en vérifiant son email, son mot de passe et son rôle
    if email == SUPER_ADMIN_USERNAME and password == SUPER_ADMIN_PASSWORD:
        return True
    return False

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub: str = payload.get("sub")
        if sub is None:
            raise InvalidTokenError("Token invalide : champ 'sub' manquant")
        return payload
    except InvalidTokenError as e:
        raise INVALID_TOKEN_EXCEPTION
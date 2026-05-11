import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt

from api.database import get_db
from api.models import User as DBUser
from api.schemas import UserCreate, UserLogin, UserUpdate, Token, User

# Require JWT_SECRET at runtime; no fallback for security
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET environment variable is required but not set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

router = APIRouter(prefix="/auth", tags=["auth"])

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(DBUser).filter(DBUser.username == username).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=User)
def register(user: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    db_user = db.query(DBUser).filter(DBUser.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = pwd_context.hash(user.password)
    new_user = DBUser(
        username=user.username,
        hashed_password=hashed_password,
        telegram_username=user.telegram_username
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    if new_user.telegram_username:
        from api.telegram_bot import send_telegram_alert
        msg = f"🎉 Welcome to Quantify, {new_user.username}!\n\nYour Telegram account is now connected to your dashboard. You will receive automated alerts here whenever you log a new trade and when it's time to sell."
        background_tasks.add_task(send_telegram_alert, new_user.telegram_username, msg)
        
    return new_user

@router.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(DBUser).filter(DBUser.username == user.username).first()
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": db_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=User)
def get_me(current_user: DBUser = Depends(get_current_user)):
    return current_user

@router.put("/update", response_model=User)
def update_account(updates: UserUpdate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Update the current user's account settings with validated input."""
    if updates.telegram_username is not None:
        current_user.telegram_username = updates.telegram_username or None
    
    if updates.new_password:
        new_pw = updates.new_password
        if len(new_pw) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        current_user.hashed_password = pwd_context.hash(new_pw[:72])
    
    db.commit()
    db.refresh(current_user)
    return current_user

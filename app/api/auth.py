from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import get_session
from app.models import User
from app.schemas import Token, UserCreate, UserRead
from app.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter()


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(user_in: UserCreate, session: AsyncSession = Depends(get_session)):
    """Create a new user profile inside the SIEM database."""
    # Check if username already exists
    stmt = select(User).where(User.username == user_in.username)
    result = await session.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Validate role level
    allowed_roles = ["Admin", "Security Analyst", "Viewer"]
    role = user_in.role if user_in.role in allowed_roles else "Viewer"

    hashed_pw = get_password_hash(user_in.password)
    user = User(
        username=user_in.username,
        hashed_password=hashed_pw,
        role=role
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session)
):
    """Authenticate credentials and return a signed JWT token."""
    stmt = select(User).where(User.username == form_data.username)
    result = await session.execute(stmt)
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token with username subject and role claim
    token_data = {"sub": user.username, "role": user.role}
    access_token = create_access_token(data=token_data)
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        username=user.username
    )

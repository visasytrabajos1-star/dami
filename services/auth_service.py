from passlib.context import CryptContext
from sqlmodel import Session, select
from database.models import User, Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password):
        return pwd_context.hash(password)

    @staticmethod
    def create_default_user_and_settings(session: Session):
        # 1. Create Default Admin
        user = session.exec(select(User).where(User.username == "admin")).first()
        if not user:
            hashed = AuthService.get_password_hash("admin123")
            admin = User(username="admin", password_hash=hashed, role="admin", full_name="Administrador")
            session.add(admin)
            print("INFO: Created default user 'admin' with password 'admin123'")
        
        # 2. Create Default Settings
        settings = session.exec(select(Settings)).first()
        if not settings:
            default_settings = Settings(company_name="NexPos", logo_url="/static/images/logo.png")
            session.add(default_settings)
            print("INFO: Created default settings for NexPos")
            
        session.commit()

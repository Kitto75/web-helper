from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Admin(Base):
    __tablename__='admins'
    id: Mapped[int]=mapped_column(primary_key=True)
    username: Mapped[str]=mapped_column(String(64), unique=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    is_super: Mapped[bool]=mapped_column(Boolean, default=False)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    credit_toman: Mapped[float]=mapped_column(Float, default=0)
    price_per_gb: Mapped[float]=mapped_column(Float, default=100000)
    allowed_inbounds: Mapped[str]=mapped_column(Text, default='')

class UserAccount(Base):
    __tablename__='users'
    id: Mapped[int]=mapped_column(primary_key=True)
    admin_id: Mapped[int]=mapped_column(ForeignKey('admins.id'))
    username: Mapped[str]=mapped_column(String(64), unique=True)
    inbound_id: Mapped[int]=mapped_column(Integer)
    traffic_gb: Mapped[float]=mapped_column(Float)
    expiry_days: Mapped[int]=mapped_column(Integer, default=30)
    enabled: Mapped[bool]=mapped_column(Boolean, default=True)
    subscription_link: Mapped[str]=mapped_column(Text)
    config_link: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
    admin_comment: Mapped[str]=mapped_column(Text, default='')

class BalanceRequest(Base):
    __tablename__='balance_requests'
    id: Mapped[int]=mapped_column(primary_key=True)
    admin_id: Mapped[int]=mapped_column(ForeignKey('admins.id'))
    amount: Mapped[float]=mapped_column(Float)
    message: Mapped[str]=mapped_column(Text, default='')
    screenshot_path: Mapped[str]=mapped_column(String(255), default='')
    approved: Mapped[bool]=mapped_column(Boolean, default=False)

class AuditLog(Base):
    __tablename__='audit_logs'
    id: Mapped[int]=mapped_column(primary_key=True)
    actor: Mapped[str]=mapped_column(String(64))
    category: Mapped[str]=mapped_column(String(32))
    detail: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

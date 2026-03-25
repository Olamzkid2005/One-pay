"""
OnePay — SQLAlchemy declarative base.
All models import Base from here, not from each other.
"""
from sqlalchemy.orm import declarative_base

Base = declarative_base()

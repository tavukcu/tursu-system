import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'tursu-fabrika-2024-secret')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/tursu_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FIRMA_ADI = os.environ.get('FIRMA_ADI', 'Tursu Fabrikası')
    # Fix Railway's postgres:// to postgresql://
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

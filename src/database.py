from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
# acá me conecto a la base de datos usando SQLAlchemy

# dotenv para cargar las variables de entorno
load_dotenv()

# obtengo la URL de la base de datos desde el .env
DATABASE_URL = os.getenv("DATABASE_URL")

# creo el engine de SQLAlchemy con la URL de la base de datos
engine = create_engine(DATABASE_URL)

# Mi conexion la hago con sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# clase base para los modelos de SQLAlchemy
Base = declarative_base()

# obtener sesión de DB en cada request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
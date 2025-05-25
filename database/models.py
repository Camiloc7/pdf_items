# from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, inspect
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker, relationship
# from datetime import datetime
# from config.settings import settings 
# Base = declarative_base()
# class Factura(Base):
#     __tablename__ = 'facturas' 
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     numero_factura = Column(String(255), unique=True, nullable=False) 
#     fecha_emision = Column(DateTime) 
#     fecha_vencimiento = Column(DateTime)
#     monto_subtotal = Column(Float) 
#     monto_impuesto = Column(Float) 
#     monto_total = Column(Float) 
#     moneda = Column(String(10), default='COP')
#     nombre_proveedor = Column(String(255))
#     nit_proveedor = Column(String(50))
#     nombre_cliente = Column(String(255))
#     nit_cliente = Column(String(50)) 
#     cufe = Column(String(96))
#     metodo_pago = Column(String(100)) 
#     texto_crudo = Column(Text) 
#     ruta_archivo = Column(String(512), nullable=False) 
#     procesado_en = Column(DateTime, default=datetime.now) 
#     items = relationship("ItemFactura", back_populates="factura", cascade="all, delete-orphan")
#     campos_corregidos = relationship("CampoCorregido", back_populates="factura", cascade="all, delete-orphan")
#     def __repr__(self):
#         return (f"<Factura(id={self.id}, numero='{self.numero_factura}', "
#                 f"total={self.monto_total})>")
# class ItemFactura(Base):
#     __tablename__ = 'items_factura' 
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     id_factura = Column(Integer, ForeignKey('facturas.id'), nullable=False)
#     descripcion = Column(String(512)) 
#     cantidad = Column(Float) 
#     precio_unitario = Column(Float) 
#     total_linea = Column(Float) 
#     factura = relationship("Factura", back_populates="items")

#     def __repr__(self):
#         return (f"<ItemFactura(id={self.id}, id_factura={self.id_factura}, "
#                 f"descripcion='{self.descripcion}', total={self.total_linea})>")
# class CampoCorregido(Base):
#     __tablename__ = 'campos_corregidos' 

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     id_factura = Column(Integer, ForeignKey('facturas.id'), nullable=False)
#     nombre_campo = Column(String(100), nullable=False)
#     valor_original = Column(String(512))
#     valor_corregido = Column(String(512), nullable=False) 
#     fecha_correccion = Column(DateTime, default=datetime.now) 
#     factura = relationship("Factura", back_populates="campos_corregidos")

#     def __repr__(self):
#         return (f"<CampoCorregido(id_factura={self.id_factura}, campo='{self.nombre_campo}', "
#                 f"valor_corregido='{self.valor_corregido}')>")

# engine = create_engine(settings.DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# def init_db():
#     try:
#         inspector = inspect(engine)
#         if not inspector.has_table("facturas") or \
#            not inspector.has_table("items_factura") or \
#            not inspector.has_table("campos_corregidos"):
#             print("Creando tablas en la base de datos...")
#             Base.metadata.create_all(bind=engine)
#             print("Tablas creadas exitosamente.")
#         else:
#             print("Las tablas ya existen en la base de datos.")
#     except Exception as e:
#         print(f"Error al inicializar la base de datos: {e}")

# if __name__ == "__main__":
#     init_db()


from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config.settings import settings

Base = declarative_base()

class Factura(Base):
    __tablename__ = 'facturas'

    id = Column(Integer, primary_key=True, autoincrement=True)
    numero_factura = Column(String(255), unique=True, nullable=False)
    fecha_emision = Column(DateTime)
    fecha_vencimiento = Column(DateTime)
    monto_subtotal = Column(Float)
    monto_impuesto = Column(Float)
    monto_total = Column(Float)
    moneda = Column(String(10), default='COP')
    nombre_proveedor = Column(String(255))
    nit_proveedor = Column(String(50))
    nombre_cliente = Column(String(255))
    nit_cliente = Column(String(50))
    cufe = Column(String(96))
    metodo_pago = Column(String(100))
    texto_crudo = Column(Text)
    ruta_archivo = Column(String(512), nullable=False)
    procesado_en = Column(DateTime, default=datetime.now)

    items = relationship("ItemFactura", back_populates="factura", cascade="all, delete-orphan")
    campos_corregidos = relationship("CampoCorregido", back_populates="factura", cascade="all, delete-orphan")
    items_corregidos = relationship("ItemCorregido", back_populates="factura", cascade="all, delete-orphan") # Nueva relación

    def __repr__(self):
        return (f"<Factura(id={self.id}, numero='{self.numero_factura}', "
                f"total={self.monto_total})>")

class ItemFactura(Base):
    __tablename__ = 'items_factura'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_factura = Column(Integer, ForeignKey('facturas.id'), nullable=False)
    descripcion = Column(String(512))
    cantidad = Column(Float)
    precio_unitario = Column(Float)
    total_linea = Column(Float)

    factura = relationship("Factura", back_populates="items")
    # Si quieres que las correcciones de items_factura puedan referenciar al item específico, añade esta relación
    # correcciones_item = relationship("ItemCorregido", back_populates="item_factura_asociado", cascade="all, delete-orphan")

    def __repr__(self):
        return (f"<ItemFactura(id={self.id}, id_factura={self.id_factura}, "
                f"descripcion='{self.descripcion}', total={self.total_linea})>")

class CampoCorregido(Base):
    __tablename__ = 'campos_corregidos'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_factura = Column(Integer, ForeignKey('facturas.id'), nullable=False)
    nombre_campo = Column(String(100), nullable=False)
    valor_original = Column(String(512))
    valor_corregido = Column(String(512), nullable=False)
    fecha_correccion = Column(DateTime, default=datetime.now)

    factura = relationship("Factura", back_populates="campos_corregidos")

    def __repr__(self):
        return (f"<CampoCorregido(id_factura={self.id_factura}, campo='{self.nombre_campo}', "
                f"valor_corregido='{self.valor_corregido}')>")

# NUEVA TABLA para correcciones de ítems de línea
class ItemCorregido(Base):
    __tablename__ = 'items_corregidos'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_factura = Column(Integer, ForeignKey('facturas.id'), nullable=False)
    # Referencia opcional al ID del item original en la tabla ItemFactura, si la corrección es sobre uno existente
    id_item_original = Column(Integer, ForeignKey('items_factura.id'), nullable=True)
    tipo_correccion = Column(String(50), nullable=False) # 'actualizar', 'añadir', 'eliminar'
    campo_corregido = Column(String(100)) # 'descripcion', 'cantidad', 'precio_unitario', 'total_linea'
    valor_original = Column(Text) # Puede ser un JSON si es un ítem completo
    valor_corregido = Column(Text, nullable=False) # Puede ser un JSON si es un ítem completo
    fecha_correccion = Column(DateTime, default=datetime.now)

    factura = relationship("Factura", back_populates="items_corregidos")
    # item_factura_asociado = relationship("ItemFactura", back_populates="correcciones_item") # Descomentar si la relación es bidireccional

    def __repr__(self):
        return (f"<ItemCorregido(id_factura={self.id_factura}, tipo='{self.tipo_correccion}', "
                f"campo='{self.campo_corregido}', valor_corregido='{self.valor_corregido[:50]}...')>")


engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    try:
        inspector = inspect(engine)
        # Verificar si todas las tablas existen para evitar recrear
        required_tables = ["facturas", "items_factura", "campos_corregidos", "items_corregidos"]
        if not all(inspector.has_table(table_name) for table_name in required_tables):
            print("Creando o actualizando tablas en la base de datos...")
            Base.metadata.create_all(bind=engine)
            print("Tablas creadas/actualizadas exitosamente.")
        else:
            print("Las tablas ya existen en la base de datos.")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

if __name__ == "__main__":
    init_db()
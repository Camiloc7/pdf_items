import os
from imap_tools import MailBox
import tempfile
import shutil
import re
import logging 
from database.models import SessionLocal, Usuario 
from config.settings import settings 
from ingestion.utils import cargar_uids_procesados, guardar_uid
logger = logging.getLogger(__name__) 
def contiene_factura(texto):
    texto = texto.lower()
    palabras_clave = ["factura", "invoice", "comprobante", "recibo", "cuenta", "estado de cuenta", "billing", "cxc", "facturación", "orden de compra", "remisión", "nota crédito", "nota débito"]
    return any(palabra in texto for palabra in palabras_clave)
def obtener_usuarios_db():
    session = SessionLocal()
    usuarios_list = []
    try:
        usuarios_orm = session.query(Usuario).all()
        for user_obj in usuarios_orm:
            usuarios_list.append({
                "correo": user_obj.correo,
                "password": user_obj.contrasena 
            })
    except Exception as e:
        logger.error(f"Error al obtener usuarios de la base de datos con SQLAlchemy: {e}", exc_info=True)
    finally:
        session.close()
    return usuarios_list
def obtener_correos_con_facturas():
    correos = []
    usuarios = obtener_usuarios_db()

    if not usuarios:
        logger.warning("No se encontraron usuarios configurados en la base de datos para la lectura de correos.")
        return []

    for usuario in usuarios:
        email = usuario.get("correo")
        password = usuario.get("password")

        if not email or not password:
            logger.warning(f"Usuario sin correo o contraseña, se omite: {email}")
            continue

        logger.info(f"Buscando correos para: {email}")
        uids_procesados = cargar_uids_procesados(email)

        try:
            imap_server = settings.EMAIL_IMAP_SERVER 
            with MailBox(imap_server).login(email, password, 'INBOX') as mailbox:
                for msg in mailbox.fetch(reverse=True, limit=settings.EMAIL_FETCH_LIMIT): 
                    if str(msg.uid) in uids_procesados:
                        continue
                    cuerpo = msg.text or msg.html or ""
                    asunto = msg.subject or ""
                    if contiene_factura(cuerpo) or contiene_factura(asunto):
                        adjuntos_procesados_temp_paths = []
                        temp_dir_for_attachments = None 
                        for att in msg.attachments:
                            if att.filename.lower().endswith(('.pdf', '.zip')):
                                if not temp_dir_for_attachments:
                                    temp_dir_for_attachments = tempfile.mkdtemp()
                                path = os.path.join(temp_dir_for_attachments, f"{msg.uid}_{att.filename}")
                                with open(path, 'wb') as f:
                                    f.write(att.payload)
                                adjuntos_procesados_temp_paths.append(path)
                                logger.info(f"    Adjunto guardado temporalmente: {path}")

                        if adjuntos_procesados_temp_paths:
                            correos.append({
                                "from": msg.from_,
                                "subject": asunto,
                                "uid": msg.uid,
                                "adjuntos_temp_paths": adjuntos_procesados_temp_paths, 
                                "correo_cliente": email 
                            })
                            guardar_uid(str(msg.uid), email)
                            logger.info(f"  Correo UID {msg.uid} de '{email}' marcado como procesado.")
        except Exception as e:
            logger.error(f"Error al obtener correos para {email}: {e}", exc_info=True)
    return correos
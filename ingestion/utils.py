import os
import re

def sanitize_email(email):
    return re.sub(r'[^a-zA-Z0-9]', '_', email)
def cargar_uids_procesados(email=None):
    archivo = "uids_procesados.txt"
    if email:
        archivo = f"uids_procesados_{sanitize_email(email)}.txt"
    if not os.path.exists(archivo):
        return set()
    with open(archivo, "r") as f:
        return set(line.strip() for line in f if line.strip())

def guardar_uid(uid, email=None):
    archivo = "uids_procesados.txt"
    if email:
        archivo = f"uids_procesados_{sanitize_email(email)}.txt"
    with open(archivo, "a") as f:
        f.write(f"{uid}\n")

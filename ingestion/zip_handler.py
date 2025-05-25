import zipfile
import tempfile
import os

def extraer_pdfs_de_zip(ruta_zip):
    pdfs = []
    with zipfile.ZipFile(ruta_zip, 'r') as archivo_zip:
        for nombre in archivo_zip.namelist():
            if nombre.lower().endswith('.pdf'):
                with archivo_zip.open(nombre) as archivo:
                    temp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                    temp.write(archivo.read())
                    temp.close()
                    pdfs.append(temp.name)
    return pdfs
 
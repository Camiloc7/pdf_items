# import zipfile
# import tempfile
# import os

# def extraer_pdfs_de_zip(ruta_zip):
#     pdfs = []
#     with zipfile.ZipFile(ruta_zip, 'r') as archivo_zip:
#         for nombre in archivo_zip.namelist():
#             if nombre.lower().endswith('.pdf'):
#                 with archivo_zip.open(nombre) as archivo:
#                     temp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
#                     temp.write(archivo.read())
#                     temp.close()
#                     pdfs.append(temp.name)
#     return pdfs

 
import zipfile
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

def extraer_archivos_de_zip(ruta_zip: str):
    temp_dir = tempfile.mkdtemp()
    extracted_paths = {'pdfs': [], 'xmls': []}
    try:
        with zipfile.ZipFile(ruta_zip, 'r') as archivo_zip:
            for nombre in archivo_zip.namelist():
                if nombre.endswith('/'):
                    continue
                nombre_base = os.path.basename(nombre)
                temp_file_path = os.path.join(temp_dir, nombre_base)
                with archivo_zip.open(nombre) as archivo_en_zip:
                    with open(temp_file_path, 'wb') as temp_f:
                        temp_f.write(archivo_en_zip.read())
                if nombre.lower().endswith('.pdf'):
                    extracted_paths['pdfs'].append(temp_file_path)
                elif nombre.lower().endswith('.xml'):
                    extracted_paths['xmls'].append(temp_file_path)
                else:
                    logger.info(f"Archivo no procesado en ZIP: {nombre}")
    except Exception as e:
        logger.error(f"Error al extraer de ZIP {ruta_zip}: {e}", exc_info=True)
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
        return {'pdfs': [], 'xmls': [], 'temp_dir': None}
    return {'pdfs': extracted_paths['pdfs'], 'xmls': extracted_paths['xmls'], 'temp_dir': temp_dir}
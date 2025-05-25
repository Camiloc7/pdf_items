# import logging
# import camelot
# import tabula
# import pandas as pd
# from typing import List, Dict, Any, Optional
# import re 
# logger = logging.getLogger(__name__)
# class TableExtractor:
#     def __init__(self):
#         pass
#     def extract_tables_camelot(self, pdf_path: str, flavor: str = 'lattice') -> List[pd.DataFrame]:
#         tables = []
#         try:
#             if flavor == 'lattice':
#                 extracted_tables = camelot.read_pdf(pdf_path, pages='all', flavor=flavor,
#                                                     line_scale=40)
#             elif flavor == 'stream':
#                 extracted_tables = camelot.read_pdf(pdf_path, pages='all', flavor=flavor,
#                                                     row_tol=10)
#             else:
#                 raise ValueError("Flavor no válido para Camelot. Debe ser 'lattice' o 'stream'.")
#             logger.info(f"Camelot extrajo {len(extracted_tables)} tablas del PDF '{pdf_path}' con flavor '{flavor}'.")
#             for table in extracted_tables:
#                 tables.append(table.df)
#         except Exception as e:
#             logger.warning(f"Error al extraer tablas con Camelot (flavor '{flavor}') de '{pdf_path}': {e}")
#         return tables

#     def extract_tables_tabula(self, pdf_path: str) -> List[pd.DataFrame]:
#         tables = []
#         try:
#             df_list = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True,
#                                       guess=True, stream=True, encoding='utf-8')
#             logger.info(f"Tabula-py extrajo {len(df_list)} tablas del PDF '{pdf_path}'.")
#             tables.extend(df_list)
#         except Exception as e:
#             logger.warning(f"Error al extraer tablas con Tabula-py de '{pdf_path}': {e}. Asegúrate de que Java esté instalado y configurado en tu PATH.")
#         return tables

#     def extract_and_parse_line_items(self, pdf_path: str) -> List[Dict[str, Any]]:      
#         all_extracted_items: List[Dict[str, Any]] = []
#         logger.debug(f"Intentando extracción de tablas con Camelot (lattice) para {pdf_path}")
#         camelot_lattice_tables = self.extract_tables_camelot(pdf_path, flavor='lattice')
#         for df in camelot_lattice_tables:
#             parsed_items = self._parse_dataframe_to_line_items(df)
#             if parsed_items:
#                 all_extracted_items.extend(parsed_items)
#                 logger.info(f"Extraídos {len(parsed_items)} ítems con Camelot Lattice.")
#                 return all_extracted_items 
#         logger.debug(f"Intentando extracción de tablas con Camelot (stream) para {pdf_path}")
#         camelot_stream_tables = self.extract_tables_camelot(pdf_path, flavor='stream')
#         for df in camelot_stream_tables:
#             parsed_items = self._parse_dataframe_to_line_items(df)
#             if parsed_items:
#                 all_extracted_items.extend(parsed_items)
#                 logger.info(f"Extraídos {len(parsed_items)} ítems con Camelot Stream.")
#                 return all_extracted_items 
#         logger.debug(f"Intentando extracción de tablas con Tabula-py para {pdf_path}")
#         tabula_tables = self.extract_tables_tabula(pdf_path)
#         for df in tabula_tables:
#             parsed_items = self._parse_dataframe_to_line_items(df)
#             if parsed_items:
#                 all_extracted_items.extend(parsed_items)
#                 logger.info(f"Extraídos {len(parsed_items)} ítems con Tabula-py.")
#                 return all_extracted_items 
#         logger.warning(f"No se pudieron extraer ítems de línea en formato de tabla para {pdf_path} con las estrategias actuales.")
#         return all_extracted_items
#     def _parse_dataframe_to_line_items(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
#         items: List[Dict[str, Any]] = []
#         original_columns = df.columns.tolist()
#         df.columns = [str(col).strip().lower().replace(' ', '_').replace('.', '').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u') for col in df.columns]
#         logger.debug(f"Columnas originales de la tabla: {original_columns}")
#         logger.debug(f"Columnas normalizadas de la tabla: {df.columns.tolist()}")
#         col_mapping = {
#             'description': ['descripcion', 'description', 'detalle', 'concepto', 'item', 'desc'],
#             'quantity': ['cantidad', 'qty', 'quantity', 'cant'],
#             'unit_price': ['precio_unitario', 'unitario', 'precio_unit', 'unit_price', 'valor_unitario', 'vrunitario', 'p_unit'],
#             'line_total': ['total', 'valor_total', 'subtotal', 'importe', 'vr_total', 'total_linea']
#         }
#         detected_cols = {}
#         for std_col, possible_names in col_mapping.items():
#             for name in possible_names:
#                 if name in df.columns:
#                     detected_cols[std_col] = name
#                     break
#         logger.debug(f"Columnas estandarizadas detectadas en la tabla: {detected_cols}")
#         if 'description' not in detected_cols or 'quantity' not in detected_cols or 'unit_price' not in detected_cols:
#             logger.warning("No se pudieron identificar las columnas necesarias (description, quantity, unit_price) por nombre. Intentando por índice.")
        
#             if len(df.columns) > 3 and df.columns[0] == '0':
#                 detected_cols['description'] = df.columns[1] 
#                 detected_cols['quantity'] = df.columns[2] 
#                 detected_cols['unit_price'] = df.columns[3]
#                 if len(df.columns) > 4:
#                     detected_cols['line_total'] = df.columns[4]
#             if 'description' not in detected_cols or 'quantity' not in detected_cols or 'unit_price' not in detected_cols:
#                 logger.warning(f"No se pudieron establecer todas las columnas necesarias para los ítems después de intentar por nombre y por índice. Columnas disponibles: {df.columns.tolist()}")
#                 return []
#         for index, row in df.iterrows():
#             try:
#                 description = str(row.get(detected_cols.get('description'), '')).strip()
#                 quantity = self._safe_parse_amount(row.get(detected_cols.get('quantity')))
#                 unit_price = self._safe_parse_amount(row.get(detected_cols.get('unit_price')))
#                 line_total = self._safe_parse_amount(row.get(detected_cols.get('line_total')))
#                 if (description and description.lower() not in ['item', 'ítem', 'description', 'descripcion', 'concepto', 'total'] and
#                     (quantity is not None and quantity > 0) or
#                     (unit_price is not None and unit_price > 0)):
#                     if line_total is None and quantity is not None and unit_price is not None:
#                         line_total = round(quantity * unit_price, 2) 
#                     item = {
#                         "description": description,
#                         "quantity": quantity,
#                         "unit_price": unit_price,
#                         "line_total": line_total
#                     }
#                     items.append(item)
#                     logger.debug(f"Ítem de tabla parseado y añadido: {item}")
#                 else:
#                     logger.debug(f"Fila de tabla filtrada (posiblemente ruido o datos incompletos/encabezado/pie): {row.to_dict()}")
#             except Exception as e:
#                 logger.warning(f"Error al procesar fila '{row.to_dict()}' a ítem: {e}")
#         return items

#     def _safe_parse_amount(self, value: Any) -> Optional[float]:
#         """Envuelve _parse_amount para manejar valores NaN o no string de Pandas."""
#         if pd.isna(value):
#             return None
#         return self._parse_amount(str(value))
#     def _parse_amount(self, value: str) -> Optional[float]:
#         value = value.strip()
#         if not value:
#             return None
#         value = re.sub(r'^(?:€|\$|EUR|USD|MXN|COP)\s*', '', value)
#         if ',' in value and '.' in value:
#             if value.rfind(',') > value.rfind('.'):
#                 value = value.replace('.', '').replace(',', '.')
#             else:
#                 value = value.replace(',', '')
#         elif ',' in value: 
#             value = value.replace(',', '.')
        
#         elif value.count('.') > 1:
#             parts = value.split('.')

#             if len(parts[-1]) > 2: 
#                 value = "".join(parts)
#             else: 
#                 value = "".join(parts[:-1]) + "." + parts[-1]
#         try:
#             return float(value)
#         except ValueError:
#             logger.debug(f"No se pudo convertir el monto '{value}' a float en table_extractor.")
#             return None



import logging
import camelot
import tabula
import pandas as pd
from typing import List, Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

class TableExtractor:
    def __init__(self):
        pass

    def extract_tables_camelot(self, pdf_path: str, flavor: str = 'lattice') -> List[pd.DataFrame]:
        tables = []
        try:
            if flavor == 'lattice':
                extracted_tables = camelot.read_pdf(pdf_path, pages='all', flavor=flavor,
                                                    line_scale=40)
            elif flavor == 'stream':
                extracted_tables = camelot.read_pdf(pdf_path, pages='all', flavor=flavor,
                                                    row_tol=10)
            else:
                raise ValueError("Flavor no válido para Camelot. Debe ser 'lattice' o 'stream'.")
            logger.info(f"Camelot extrajo {len(extracted_tables)} tablas del PDF '{pdf_path}' con flavor '{flavor}'.")
            for table in extracted_tables:
                tables.append(table.df)
        except Exception as e:
            logger.warning(f"Error al extraer tablas con Camelot (flavor '{flavor}') de '{pdf_path}': {e}")
        return tables

    def extract_tables_tabula(self, pdf_path: str) -> List[pd.DataFrame]:
        tables = []
        try:
            df_list = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True,
                                      guess=True, stream=True, encoding='utf-8')
            logger.info(f"Tabula-py extrajo {len(df_list)} tablas del PDF '{pdf_path}'.")
            tables.extend(df_list)
        except Exception as e:
            logger.warning(f"Error al extraer tablas con Tabula-py de '{pdf_path}': {e}. Asegúrate de que Java esté instalado y configurado en tu PATH.")
        return tables

    def extract_and_parse_line_items(self, pdf_path: str) -> List[Dict[str, Any]]:
        all_potential_items: List[Dict[str, Any]] = []

        logger.debug(f"Intentando extracción de tablas con Camelot (lattice) para {pdf_path}")
        camelot_lattice_tables = self.extract_tables_camelot(pdf_path, flavor='lattice')
        for df in camelot_lattice_tables:
            parsed_items = self._parse_dataframe_to_line_items(df)
            if parsed_items:
                all_potential_items.extend(parsed_items)
                logger.info(f"Extraídos {len(parsed_items)} ítems con Camelot Lattice.")

        logger.debug(f"Intentando extracción de tablas con Camelot (stream) para {pdf_path}")
        camelot_stream_tables = self.extract_tables_camelot(pdf_path, flavor='stream')
        for df in camelot_stream_tables:
            parsed_items = self._parse_dataframe_to_line_items(df)
            if parsed_items:
                all_potential_items.extend(parsed_items)
                logger.info(f"Extraídos {len(parsed_items)} ítems con Camelot Stream.")

        logger.debug(f"Intentando extracción de tablas con Tabula-py para {pdf_path}")
        tabula_tables = self.extract_tables_tabula(pdf_path)
        for df in tabula_tables:
            parsed_items = self._parse_dataframe_to_line_items(df)
            if parsed_items:
                all_potential_items.extend(parsed_items)
                logger.info(f"Extraídos {len(parsed_items)} ítems con Tabula-py.")

        if not all_potential_items:
            logger.warning(f"No se pudieron extraer ítems de línea en formato de tabla para {pdf_path} con las estrategias actuales.")
            return []

        unique_items = self._deduplicate_and_prioritize_items(all_potential_items)
        logger.info(f"Después de deduplicación, se tienen {len(unique_items)} ítems únicos.")
        return unique_items

    def _deduplicate_and_prioritize_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique_items_map = {}
        for item in items:
            key = (item.get("description"), item.get("quantity"), item.get("unit_price"))
            if key not in unique_items_map:
                unique_items_map[key] = item
            else:
                current_item = unique_items_map[key]
                if current_item.get("line_total") is None and item.get("line_total") is not None:
                    unique_items_map[key] = item
        return list(unique_items_map.values())

    def _parse_dataframe_to_line_items(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        original_columns = df.columns.tolist()
        df.columns = [str(col).strip().lower().replace(' ', '_').replace('.', '').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u') for col in df.columns]
        logger.debug(f"Columnas originales de la tabla: {original_columns}")
        logger.debug(f"Columnas normalizadas de la tabla: {df.columns.tolist()}")
        col_mapping = {
            'description': ['descripcion', 'description', 'detalle', 'concepto', 'item', 'desc'],
            'quantity': ['cantidad', 'qty', 'quantity', 'cant'],
            'unit_price': ['precio_unitario', 'unitario', 'precio_unit', 'unit_price', 'valor_unitario', 'vrunitario', 'p_unit'],
            'line_total': ['total', 'valor_total', 'subtotal', 'importe', 'vr_total', 'total_linea']
        }
        detected_cols = {}
        for std_col, possible_names in col_mapping.items():
            for name in possible_names:
                if name in df.columns:
                    detected_cols[std_col] = name
                    break
        logger.debug(f"Columnas estandarizadas detectadas en la tabla: {detected_cols}")

        if 'description' not in detected_cols or 'quantity' not in detected_cols or 'unit_price' not in detected_cols:
            logger.warning("No se pudieron identificar las columnas necesarias (description, quantity, unit_price) por nombre. Intentando por índice.")

            # Intentar mapeo por índice si no se encontraron por nombre
            # Asumiendo un orden común: Descripción, Cantidad, Precio Unitario, Total de Línea
            if len(df.columns) >= 4:
                detected_cols['description'] = df.columns[0]
                detected_cols['quantity'] = df.columns[1]
                detected_cols['unit_price'] = df.columns[2]
                detected_cols['line_total'] = df.columns[3]
            elif len(df.columns) == 3: # Si solo hay 3 columnas, asumimos descripción, cantidad, precio unitario
                detected_cols['description'] = df.columns[0]
                detected_cols['quantity'] = df.columns[1]
                detected_cols['unit_price'] = df.columns[2]

            if 'description' not in detected_cols or 'quantity' not in detected_cols or 'unit_price' not in detected_cols:
                logger.warning(f"No se pudieron establecer todas las columnas necesarias para los ítems después de intentar por nombre y por índice. Columnas disponibles: {df.columns.tolist()}")
                return []

        for index, row in df.iterrows():
            try:
                description = str(row.get(detected_cols.get('description'), '')).strip()
                quantity = self._safe_parse_amount(row.get(detected_cols.get('quantity')))
                unit_price = self._safe_parse_amount(row.get(detected_cols.get('unit_price')))
                line_total = self._safe_parse_amount(row.get(detected_cols.get('line_total')))

                if (description and description.lower() not in ['item', 'ítem', 'description', 'descripcion', 'concepto', 'total'] and
                    ((quantity is not None and quantity > 0) or
                     (unit_price is not None and unit_price > 0) or
                     (line_total is not None and line_total > 0))): # Mejorar condición para incluir si solo tiene total
                    if line_total is None and quantity is not None and unit_price is not None:
                        line_total = round(quantity * unit_price, 2)

                    item = {
                        "description": description,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "line_total": line_total
                    }
                    items.append(item)
                    logger.debug(f"Ítem de tabla parseado y añadido: {item}")
                else:
                    logger.debug(f"Fila de tabla filtrada (posiblemente ruido o datos incompletos/encabezado/pie): {row.to_dict()}")
            except Exception as e:
                logger.warning(f"Error al procesar fila '{row.to_dict()}' a ítem: {e}")
        return items

    def _safe_parse_amount(self, value: Any) -> Optional[float]:
        if pd.isna(value):
            return None
        return self._parse_amount(str(value))

    def _parse_amount(self, value: str) -> Optional[float]:
        value = value.strip()
        if not value:
            return None
        value = re.sub(r'^(?:€|\$|EUR|USD|MXN|COP)\s*', '', value)
        if ',' in value and '.' in value:
            if value.rfind(',') > value.rfind('.'):
                value = value.replace('.', '').replace(',', '.')
            else:
                value = value.replace(',', '')
        elif ',' in value:
            value = value.replace(',', '.')
        elif value.count('.') > 1:
            parts = value.split('.')
            if len(parts[-1]) > 2:
                value = "".join(parts)
            else:
                value = "".join(parts[:-1]) + "." + parts[-1]
        try:
            return float(value)
        except ValueError:
            logger.debug(f"No se pudo convertir el monto '{value}' a float en table_extractor.")
            return None
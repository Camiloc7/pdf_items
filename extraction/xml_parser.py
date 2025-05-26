import xml.etree.ElementTree as ET
import re
import logging
from typing import Dict, Any, Optional, List
logger = logging.getLogger(__name__)
def clean_and_parse_xml_string(xml_string: str):
    cleaned_xml_string = re.sub(r'[^\x09\x0A\x0D\x20-\x7E\x80-\xFF]+', ' ', xml_string)
    try:
        return ET.fromstring(cleaned_xml_string)
    except ET.ParseError as e:
        logger.error(f"Error al parsear XML después de limpieza: {e}")
        return None
def extract_nested_invoice_xml(attached_document_xml_path: str) -> Optional[str]:
    namespaces = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'ds': 'http://www.w3.org/2000/09/xmldsig#'
    }
    try:
        tree = ET.parse(attached_document_xml_path)
        root = tree.getroot()

        description_node = root.find('.//cac:Attachment/cac:ExternalReference/cbc:Description', namespaces)
        if description_node is not None and description_node.text:
            return description_node.text
    except ET.ParseError as e:
        logger.error(f"Error al parsear el XML del AttachedDocument: {e}")
    except Exception as e:
        logger.error(f"Error inesperado al extraer XML anidado: {e}")
    return None

def parse_invoice_xml(xml_content: str) -> Optional[Dict[str, Any]]:
    """
    Parsea un XML de factura electrónica colombiana (UBL) y extrae datos clave.
    """
    namespaces = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'sts': 'urn:dian:gov:co:facturaelectronica:Structures-2-1',
        'ds': 'http://www.w3.org/2000/09/xmldsig#'
    }
    root = clean_and_parse_xml_string(xml_content)
    if root is None:
        return None

    invoice_data = {}

    try:
        invoice_data['cufe'] = root.find('.//cbc:UUID', namespaces).text if root.find('.//cbc:UUID', namespaces) is not None else None
        invoice_data['numero_factura'] = root.find('.//cbc:ID', namespaces).text if root.find('.//cbc:ID', namespaces) is not None else None
        invoice_data['fecha_emision'] = root.find('.//cbc:IssueDate', namespaces).text if root.find('.//cbc:IssueDate', namespaces) is not None else None
        invoice_data['hora_emision'] = root.find('.//cbc:IssueTime', namespaces).text if root.find('.//cbc:IssueTime', namespaces) is not None else None
        invoice_data['moneda'] = root.find('.//cbc:DocumentCurrencyCode', namespaces).text if root.find('.//cbc:DocumentCurrencyCode', namespaces) is not None else None
        supplier_party = root.find('.//cac:AccountingSupplierParty/cac:Party', namespaces)
        if supplier_party:
            invoice_data['nombre_proveedor'] = supplier_party.find('.//cbc:RegistrationName', namespaces).text if supplier_party.find('.//cbc:RegistrationName', namespaces) is not None else None
            invoice_data['nit_proveedor'] = supplier_party.find('.//cbc:CompanyID', namespaces).text if supplier_party.find('.//cbc:CompanyID', namespaces) is not None else None
            supplier_email_node = supplier_party.find('.//cac:Contact/cbc:ElectronicMail', namespaces)
            invoice_data['email_proveedor'] = supplier_email_node.text if supplier_email_node is not None else None
        customer_party = root.find('.//cac:AccountingCustomerParty/cac:Party', namespaces)
        if customer_party:
            invoice_data['nombre_cliente'] = customer_party.find('.//cbc:RegistrationName', namespaces).text if customer_party.find('.//cbc:RegistrationName', namespaces) is not None else None
            invoice_data['nit_cliente'] = customer_party.find('.//cbc:CompanyID', namespaces).text if customer_party.find('.//cbc:CompanyID', namespaces) is not None else None
            customer_email_node = customer_party.find('.//cac:Contact/cbc:ElectronicMail', namespaces)
            invoice_data['correo_cliente'] = customer_email_node.text if customer_email_node is not None else None
        legal_monetary_total = root.find('.//cac:LegalMonetaryTotal', namespaces)
        if legal_monetary_total:
            invoice_data['monto_subtotal'] = legal_monetary_total.find('.//cbc:LineExtensionAmount', namespaces).text if legal_monetary_total.find('.//cbc:LineExtensionAmount', namespaces) is not None else None
            total_tax_amount_node = root.find('.//cac:TaxTotal/cbc:TaxAmount', namespaces)
            invoice_data['monto_impuesto'] = total_tax_amount_node.text if total_tax_amount_node is not None else None
            invoice_data['monto_total'] = legal_monetary_total.find('.//cbc:PayableAmount', namespaces).text if legal_monetary_total.find('.//cbc:PayableAmount', namespaces) is not None else None
        payment_means_node = root.find('.//cac:PaymentMeans/cbc:PaymentDueDate', namespaces)
        invoice_data['fecha_vencimiento'] = payment_means_node.text if payment_means_node is not None else None
        invoice_data['items'] = []
        invoice_lines = root.findall('.//cac:InvoiceLine', namespaces)
        for line in invoice_lines:
            item = {
                'id': line.find('.//cbc:ID', namespaces).text if line.find('.//cbc:ID', namespaces) is not None else None,
                'cantidad': line.find('.//cbc:InvoicedQuantity', namespaces).text if line.find('.//cbc:InvoicedQuantity', namespaces) is not None else None,
                'descripcion': line.find('.//cac:Item/cbc:Description', namespaces).text if line.find('.//cac:Item/cbc:Description', namespaces) is not None else None,
                'precio_unitario': line.find('.//cac:Price/cbc:PriceAmount', namespaces).text if line.find('.//cac:Price/cbc:PriceAmount', namespaces) is not None else None,
                'total_linea': line.find('.//cbc:LineExtensionAmount', namespaces).text if line.find('.//cbc:LineExtensionAmount', namespaces) is not None else None,
            }
            invoice_data['items'].append(item)

        logger.info("Datos extraídos del XML:")
        for key, value in invoice_data.items():
            if key != 'items':
                logger.info(f"  {key}: {value}")
            else:
                logger.info("  Items:")
                for i, item in enumerate(value):
                    logger.info(f"    Item {i+1}: {item}")
        return invoice_data
    except Exception as e:
        logger.error(f"Error al extraer datos del XML: {e}", exc_info=True)
        return None
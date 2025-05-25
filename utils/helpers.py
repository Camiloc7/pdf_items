def load_json(file_path):
    """Load a JSON file and return its contents."""
    import json
    with open(file_path, 'r') as file:
        return json.load(file)
def save_json(data, file_path):
    """Save data to a JSON file."""
    import json
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)
def format_currency(amount):
    """Format a number as currency."""
    return "${:,.2f}".format(amount)
def validate_invoice_data(data):
    """Validate the structure of invoice data."""
    required_fields = ['invoice_number', 'date', 'total_amount', 'items']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    return True
def extract_filename_without_extension(file_path):
    """Extract the filename without its extension from a file path."""
    import os
    return os.path.splitext(os.path.basename(file_path))[0]
# Invoice Parser Application

This project is an invoice parser application designed to extract and process data from PDF invoices. It utilizes various extraction techniques, including direct PDF reading, OCR, and natural language processing, to ensure accurate data retrieval.

## Project Structure

The project is organized into several directories and files, each serving a specific purpose:

- **invoice_parser/**: The main package containing the application code.
  - **main.py**: The entry point of the application.
  - **config/**: Contains configuration settings.
  - **data/**: Holds sample invoices and processed data.
  - **database/**: Contains database models and CRUD operations.
  - **extraction/**: Implements various extraction methods.
  - **learning/**: Manages feedback for incremental learning.
  - **utils/**: Contains utility functions.
  - **tests/**: Includes unit and integration tests.

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd invoice_parser
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the application, execute the following command:
```
python main.py
```

## Testing

To run the tests, use:
```
pytest tests/
```

## Contributing

Contributions are welcome! Please submit a pull request or open an issue for any suggestions or improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
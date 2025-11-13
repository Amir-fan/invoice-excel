# Invoice2Excel

A modern web application that extracts structured data from Arabic/English invoices using AI and converts them to organized Excel files.

## Features

- 📄 **Multiple Invoice Processing** - Upload and process multiple invoices at once
- 🤖 **AI-Powered Extraction** - Uses GPT-4o vision to extract invoice data accurately
- 📊 **Excel Output** - Generates clean Excel files with Arabic headers and RTL support
- 🎨 **Modern UI** - Clean, professional interface
- 🌐 **Arabic & English** - Supports both Arabic and English invoices
- 📱 **Responsive Design** - Works on desktop and mobile devices

## Tech Stack

- **Backend**: FastAPI, Python
- **AI**: OpenAI GPT-4o Vision
- **Frontend**: HTML, CSS, JavaScript
- **Excel**: openpyxl
- **PDF Processing**: PyMuPDF

## Setup

### Prerequisites

- Python 3.11 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd invoice-to-excel
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   DEBUG=false
   ```
   
   Or copy the example:
   ```bash
   cp .env.example .env
   # Then edit .env and add your API key
   ```

4. **Run the application**
   ```bash
   python app.py
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```

5. **Open your browser**
   Navigate to `http://localhost:8000`

## Deployment

### Vercel

1. **Install Vercel CLI** (if not already installed)
   ```bash
   npm i -g vercel
   ```

2. **Deploy**
   ```bash
   vercel
   ```

3. **Set Environment Variables**
   In your Vercel dashboard:
   - Go to your project → Settings → Environment Variables
   - Add `OPENAI_API_KEY` with your OpenAI API key
   - Optionally add `DEBUG=false` for production

4. **Deploy to Production**
   ```bash
   vercel --prod
   ```

### Other Platforms

The application can be deployed to any platform that supports Python/WSGI:
- Heroku
- Railway
- Render
- AWS Lambda (with modifications)
- Google Cloud Run
- Azure App Service

## Project Structure

```
invoice-to-excel/
├── app.py              # Main FastAPI application
├── ai.py               # OpenAI integration and data extraction
├── mapping.py          # Data aggregation and Excel column mapping
├── utils.py            # Utility functions (PDF/image handling)
├── templates/
│   └── index.html     # Web interface
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables example
├── .gitignore         # Git ignore file
├── vercel.json        # Vercel deployment configuration
└── README.md          # This file
```

## API Endpoints

- `GET /` - Main web interface
- `POST /upload` - File upload and processing (supports multiple files)
- `GET /health` - Health check with dependency status
- `GET /docs` - Interactive API documentation (Swagger UI)

## Supported File Formats

- PDF (requires PyMuPDF)
- JPG/JPEG
- PNG

## Extracted Fields

The application extracts the following fields from invoices:

### Seller Information
- الاسم التجاري (Commercial Name)
- الرقم الضريبي (Tax Number)
- تسلسل مصدر الدخل (Income Source Sequence)

### Invoice Details
- رقم الفاتورة الإلكترونية (Electronic Invoice Number)
- رقم فاتورة البائع (Seller Invoice Number)
- تاريخ إصدار الفاتورة (Invoice Date)
- نوع الفاتورة (Invoice Type)
- نوع العملة (Currency)

### Buyer Information
- اسم المشتري (Buyer Name)
- رقم المشتري (Buyer Number)
- رقم الهاتف (Phone Number)
- المدينة (City)

### Line Items
- الوصف (Description)
- الكمية (Quantity)
- سعر الوحدة (Unit Price)
- المبلغ (Amount)
- الخصم (Discount)
- الاجمالي (Line Total)

### Totals
- إجمالي قيمة الفاتورة (Total Invoice Value)

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | Your OpenAI API key | Yes |
| `DEBUG` | Enable debug logging (true/false) | No (default: false) |

## Troubleshooting

### PDF Processing Not Working

If PDF processing fails:
```bash
pip install PyMuPDF
```

### OpenAI API Errors

- Ensure your API key is set correctly in environment variables
- Check your OpenAI account has sufficient credits
- Verify API key has proper permissions

### Multiple Files Not Processing

- Ensure files are valid formats (PDF, JPG, PNG)
- Check file sizes (very large files may timeout)
- Review server logs for specific errors

## License

MIT License - feel free to use this project for your own purposes.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on GitHub.

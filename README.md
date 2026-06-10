# Smart Job Assistant

An automated job application assistant that searches and applies to jobs on Naukri and LinkedIn using AI-powered matching.

## Features

- **AI-Powered Job Matching**: Uses Azure OpenAI to match your CV with job listings and provide recommendations
- **Automated Application**: Automatically applies to jobs that meet your criteria
- **Multi-Platform Support**: Works with Naukri and LinkedIn
- **Real-Time Progress Tracking**: WebSocket-based live updates in the UI
- **CV Parsing**: Extracts skills, experience, and job titles from your resume

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Google Chrome** (for browser automation)
- **Azure OpenAI API Key** (for AI-powered job matching)

## Quick Start

1. **Clone the repository**
   ```bash
   cd /Users/rsingh/Rajiv\ Work/Smart_Job_Assistant
   ```

2. **Configure environment variables**
   
   Create a `.env` file in the project root (edit the existing `.env` file):
   
   ```env
   NAUKRI_USERID=your_email@example.com
   NAUKRI_PASSWORD=your_password
   
   LINKEDIN_USERID=your_email@example.com
   LINKEDIN_PASSWORD=your_password
   
   AZURE_OPENAI_ENDPOINT=https://your-openai-endpoint.openai.azure.com/
   AZURE_OPENAI_API_KEY=your_api_key_here
   AZURE_DEPLOYMENT_NAME=gpt-4o-mini
   
   CONFIDENCE_THRESHOLD=75
   PORT_NUM=9222
   CHROME_USER_DATA_DIR=./chrome_profile
   CV_PATH=./cv/resume.pdf
   LOG_PATH=./logs/applications.json
   MAX_JOBS_PER_HOUR=30
   MAX_JOBS_PER_DAY=150
   JOB_TARGET=5
   LOCATION=gurugram
   PLATFORM_CHOICE=naukri
   
   DATABASE_URL=sqlite:///./data/smart_job_assistant.db
   CV_UPLOAD_DIR=./data/cv
   ```

3. **Run the application**
   
   Simply run the startup script:
   ```bash
   ./run.sh
   ```
   
   This will:
   - Create a Python virtual environment (if not exists)
   - Install backend dependencies
   - Initialize the database
   - Start the backend server on `http://localhost:8000`
   - Install frontend dependencies (if needed)
   - Start the frontend server on `http://localhost:5173`

4. **Access the application**
   
   - **Frontend**: http://localhost:5173
   - **Backend API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs

## Manual Setup (Alternative)

If you prefer to run the servers manually:

### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from api.database import init_db; init_db()"

# Start server
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Project Structure

```
Smart_Job_Assistant/
├── backend/                 # Python FastAPI backend
│   ├── api/                # API routes and models
│   ├── core/               # Core logic (Chrome manager, CV parser, LLM client)
│   ├── platforms/          # Platform-specific implementations (Naukri, LinkedIn)
│   ├── config/             # Configuration management
│   ├── requirements.txt    # Python dependencies
│   └── api/server.py       # FastAPI application entry point
├── frontend/               # React + TypeScript frontend
│   ├── src/
│   │   ├── api/           # API client
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── store/         # Zustand state management
│   │   └── hooks/         # Custom React hooks
│   ├── package.json       # Node.js dependencies
│   └── vite.config.ts     # Vite configuration
├── data/                  # SQLite database and uploaded CVs
├── logs/                  # Application logs
├── cv/                    # CV files
├── .env                   # Environment variables
├── run.sh                 # Startup script
└── README.md             # This file
```

## How It Works

1. **Setup**: Configure your credentials and CV in the UI
2. **Login**: Log into Naukri/LinkedIn in your Chrome browser (the automation uses your existing session)
3. **Search**: The system searches for jobs matching your criteria
4. **Match**: AI scores each job based on your CV
5. **Apply**: Automatically applies to jobs that meet your threshold
6. **Track**: Real-time progress updates in the UI

## Troubleshooting

### Chrome Not Found
- Ensure Google Chrome is installed
- On macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- On Windows: `C:\Program Files\Google\Chrome\Application\chrome.exe`
- On Linux: `/usr/bin/google-chrome` or `/usr/bin/chromium`

### Login Detection Issues
- Make sure you're logged into Naukri/LinkedIn in your Chrome browser before starting a session
- The system checks for login indicators on the page

### Database Errors
- Delete `data/smart_job_assistant.db` and restart to reinitialize
- Ensure `DATABASE_URL` in `.env` points to a valid path

## License

MIT

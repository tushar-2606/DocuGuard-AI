# DocuGuard AI

## Run locally on Windows

Install the dependencies once from the project folder:

```powershell
py -m pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
```

Then double-click `run-dev.bat`. It opens the backend and frontend in separate
terminal windows. Keep both windows open while using the app.

Open the frontend URL printed in its terminal (normally
`http://127.0.0.1:5173`). To verify the backend is running, open
`http://127.0.0.1:8000/health`; it should return a healthy status.

The Vite development server forwards `/api` requests to the backend on port
8000, so the backend must be running when you analyze a PDF.

PDF uploads are limited to 15 MB and 100 pages. Scanned PDFs without selectable
text are not supported yet.

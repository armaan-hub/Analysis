# Application Startup Fix - Summary

## Issues Identified & Fixed

### 1. **Backend Startup Timeout**
   - **Problem**: The PowerShell script was checking if the backend became ready within 60 seconds. This could be too short on slower systems or first-time initialization.
   - **Fix**: Increased timeout from 60 to 120 seconds in `run_project.ps1` (lines 91 and 119)
   - **File**: `run_project.ps1`

### 2. **Frontend API Configuration Mismatch**
   - **Problem**: Frontend `.env` file had `VITE_API_BASE_URL=http://localhost:8001` but backend runs on `localhost:8000`
   - **Fix**: Corrected to `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env`
   - **File**: `frontend/.env`

### 3. **Hardcoded Backend URLs**
   - **Problem**: Multiple React components had hardcoded URLs pointing to `http://localhost:8000`:
     - `frontend/src/components/studios/FinanceStudio/api.ts`
     - `frontend/src/components/studios/FinanceStudio/ExportsPanel/FormatPicker.tsx`
     - `frontend/src/components/studios/FinanceStudio/ReportPreview/ReportPreview.tsx`
     - `frontend/src/components/studios/FinanceStudio/ExportsPanel/ExportCard.tsx`
     - `frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/SourceDocsSidebar.tsx`
   
   - **Fix**: 
     - Created centralized API configuration file: `frontend/src/api-config.ts`
     - Updated all components to import and use `API_BASE_URL` from the config
     - Now all API calls respect the `VITE_API_BASE_URL` environment variable
   - **Files Modified**: 
     - `frontend/src/api-config.ts` (NEW)
     - `frontend/src/components/studios/FinanceStudio/api.ts`
     - `frontend/src/components/studios/FinanceStudio/ExportsPanel/FormatPicker.tsx`
     - `frontend/src/components/studios/FinanceStudio/ReportPreview/ReportPreview.tsx`
     - `frontend/src/components/studios/FinanceStudio/ExportsPanel/ExportCard.tsx`
     - `frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/SourceDocsSidebar.tsx`

## How to Run

Run either of these commands to start your application:

1. **Visible terminal** (shows all logs):
   ```
   run_project.bat
   ```

2. **Hidden** (runs in background, logs saved to files):
   ```
   run_hidden.bat
   ```

## Expected Output

- Backend will start on: `http://localhost:8000`
- Frontend will start on: `http://localhost:5173`
- API Docs available at: `http://localhost:8000/docs`

## Logs

- Backend logs: `backend_server.log`
- Frontend logs: `frontend_server.log`
- Launcher logs: `run_project.log`

## Environment Variables

You can customize the backend URL by editing:
- `frontend/.env` → `VITE_API_BASE_URL` (default: `http://localhost:8000`)

## Troubleshooting

If the application still won't start:
1. Check the logs files mentioned above
2. Verify that ports 8000 and 5173 are available
3. Ensure Python virtual environment is properly installed
4. Run `install_all_dependencies.bat` to reinstall dependencies if needed

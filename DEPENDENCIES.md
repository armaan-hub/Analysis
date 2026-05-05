# Accounting & Legal AI Chatbot — Dependency Manifest

**Last updated:** 2026-05-05

## Update Rule

> **Whenever a new library is added to requirements.txt or package.json, this file MUST be updated and committed in the same PR/commit.**

## Backend Dependencies

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | `==0.136.1` | Python web framework for backend APIs. |
| `uvicorn[standard]` | `==0.46.0` | ASGI server to run FastAPI in development/production. |
| `python-dotenv` | `==1.0.1` | Loads environment variables from .env files. |
| `pydantic` | `==2.13.3` | Data validation and schema models. |
| `pydantic-settings` | `==2.14.0` | Settings management using Pydantic models. |
| `sqlalchemy` | `==2.0.49` | ORM and SQL toolkit for database access. |
| `aiosqlite` | `==0.20.0` | Async SQLite driver support. |
| `openai` | `==1.109.1` | OpenAI API client library. |
| `anthropic` | `==0.97.0` | Anthropic API client library. |
| `httpx` | `==0.28.1` | Async HTTP client for external API calls. |
| `chromadb` | `==0.5.15` | Vector database for embeddings/RAG retrieval. |
| `PyMuPDF` | `==1.27.2` | PDF parsing and text extraction. |
| `python-docx` | `==1.1.2` | Read/write Microsoft Word documents. |
| `openpyxl` | `==3.1.5` | Read/write Excel .xlsx files. |
| `pandas` | `==2.2.3` | Data analysis and tabular transformations. |
| `scikit-learn` | `==1.6.1` | ML utilities used for data processing. |
| `pdf2image` | `==1.17.0` | Converts PDF pages to images for OCR. |
| `pytesseract` | `==0.3.13` | Python wrapper for Tesseract OCR. |
| `Pillow` | `==11.1.0` | Image processing utilities. |
| `opencv-python-headless` | `==4.10.0.84` | Computer vision/image preprocessing. |
| `deskew` | `==1.3.2` | Image deskewing for OCR preprocessing. |
| `scikit-image` | `==0.24.0` | Image processing algorithms. |
| `python-multipart` | `==0.0.20` | Multipart/form-data upload handling. |
| `aiofiles` | `==24.1.0` | Async file I/O support. |
| `reportlab` | `==4.2.5` | PDF generation for reports. |
| `xlsxwriter` | `==3.2.0` | Excel report generation. |
| `markdown` | `==3.7` | Markdown rendering/conversion support. |
| `apscheduler` | `==3.10.4` | Scheduled/background task execution. |
| `beautifulsoup4` | `==4.12.3` | HTML parsing and scraping utilities. |
| `requests` | `==2.32.3` | Synchronous HTTP client. |
| `duckduckgo-search` | `==6.3.7` | DuckDuckGo search integration. |
| `websockets` | `==14.1` | WebSocket protocol support. |
| `python-dateutil` | `==2.9.0` | Extended date/time parsing utilities. |
| `rapidfuzz` | `==3.9.7` | Fast fuzzy-string matching. |
| `watchdog` | `==4.0.1` | File system change monitoring. |
| `spacy` | `>=3.7,<4.0` | NLP toolkit for language processing. |
| `urllib3` | `>=1.26.0,<3` | HTTP transport dependency pin. |
| `charset-normalizer` | `==3.4.1` | Character encoding detection dependency pin. |
| `pytest` | `==7.4.4` | Python test runner. |
| `pytest-asyncio` | `==0.23.2` | Async support for pytest. |
| `posthog` | `==3.25.0` | Chroma telemetry compatibility dependency. |

## Frontend Dependencies

| Package | Version | Purpose |
|---|---|---|
| `@tanstack/react-table` | `^8.21.3` | Headless table state/logic for data grids. |
| `axios` | `^1.15.0` | HTTP client for API requests. |
| `lucide-react` | `^0.474.0` | Icon component library. |
| `react` | `^19.2.4` | Core UI library for frontend. |
| `react-dom` | `^19.2.4` | DOM renderer for React. |
| `react-markdown` | `^10.1.0` | Render Markdown content in React. |
| `react-router-dom` | `^7.14.0` | Client-side routing for React app. |
| `react-syntax-highlighter` | `^16.1.1` | Code block syntax highlighting. |
| `recharts` | `^3.8.1` | Charting components for React. |
| `rehype-highlight` | `^7.0.2` | Highlight.js integration for rendered HTML/Markdown. |
| `rehype-katex` | `^7.0.1` | KaTeX rendering for math in Markdown. |
| `remark-gfm` | `^4.0.1` | GitHub Flavored Markdown support. |
| `remark-math` | `^6.0.0` | Math syntax support in Markdown. |

## Frontend Dev Dependencies

| Package | Version | Purpose |
|---|---|---|
| `@eslint/js` | `^9.39.4` | ESLint core rule presets. |
| `@testing-library/dom` | `^10.4.1` | DOM testing helpers. |
| `@testing-library/jest-dom` | `^6.9.1` | Custom matchers for DOM assertions. |
| `@testing-library/react` | `^16.3.2` | React component testing utilities. |
| `@testing-library/user-event` | `^14.6.1` | High-level user interaction simulation. |
| `@types/node` | `^24.12.2` | TypeScript types for Node.js. |
| `@types/react` | `^19.2.14` | TypeScript types for React. |
| `@types/react-dom` | `^19.2.3` | TypeScript types for React DOM. |
| `@types/react-syntax-highlighter` | `^15.5.13` | Type definitions for react-syntax-highlighter. |
| `@vitejs/plugin-react` | `^6.0.1` | Vite plugin for React fast refresh/JSX. |
| `@vitest/coverage-v8` | `^4.1.5` | Code coverage provider for Vitest. |
| `@vitest/ui` | `^4.1.5` | Browser UI for Vitest runs. |
| `eslint` | `^9.39.4` | JavaScript/TypeScript linting. |
| `eslint-plugin-react-hooks` | `^7.0.1` | Lint rules for React Hooks. |
| `eslint-plugin-react-refresh` | `^0.5.2` | Lint rules for React Fast Refresh compatibility. |
| `globals` | `^17.4.0` | Shared global variable definitions for linting. |
| `happy-dom` | `^20.9.0` | Lightweight DOM implementation for tests. |
| `jsdom` | `^29.0.2` | DOM/browser emulation for tests. |
| `typescript` | `~6.0.2` | Type checking and TS language support. |
| `typescript-eslint` | `^8.58.0` | TypeScript support for ESLint. |
| `vite` | `^8.0.4` | Frontend dev server and build tool. |
| `vitest` | `^4.1.5` | Unit/integration test runner for frontend. |

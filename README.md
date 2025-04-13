# TrustIt-AI Search Application

A web search application using Portia and Tavily to provide reliable search results.

## Overview

This application integrates Portia's agent capabilities with Tavily's search API to create a powerful and trustworthy search tool. The application is designed with modularity and maintainability in mind, following software engineering best practices.

## Features

- Web search using Tavily's search API
- Agent-based search orchestration with Portia
- Command-line interface for easy search queries
- Modular codebase with separation of concerns

## Setup

### Prerequisites

- Python 3.11 or higher
- API keys for:
  - Google Generative AI (Gemini)
  - Portia
  - Tavily

### Installation

1. Clone the repository

   ```
   git clone https://github.com/yourusername/TrustIt-AI.git
   cd TrustIt-AI
   ```

2. Set up a virtual environment

   ```
   python -m venv portia-env-py311
   
   # Activate the virtual environment:
   # On Linux/Mac:
   source backend/portia-env-py311/bin/activate
   # On Windows:
   portia-env-py311\Scripts\activate

4. Install dependencies

   ```
   pip install portia-sdk-python[google] fastapi tavily-sdk pusher
   ```

5. Create a `.env` file in the project root with the following API keys:
   ```
   GOOGLE_API_KEY=your_google_api_key
   PORTIA_API_KEY=your_portia_api_key
   TAVILY_API_KEY=your_tavily_api_key
   ```

## Usage

The application now follows a two-step process:

1.  **Question Generation:** Takes your initial query and uses Google Gemini to generate several specific sub-questions.
2.  **Iterative Search:** Uses Portia and the Tavily Search tool to search the web for answers to each generated sub-question.
3.  **Aggregation:** Combines the results from all sub-searches into a final output.



## Code Structure

The application follows a modular design:

- `backend/` - Main package
  - `config.py` - Configuration loading and management
  - `main.py` - Main entry point for the application
  - `cli.py` - Command-line interface
  - `tools/` - Tool implementations
    - `tavily_search.py` - Tavily search tool implementation
  - `services/` - Service classes
    - `search_service.py` - Portia search service
  - `utils/` - Utility functions
    - `environment.py` - Environment setup utilities


## TrustIt-AI Integration with Portia

TrustIt-AI now integrates with [Portia](https://github.com/portiaAI/portia-sdk-python), an AI orchestration platform that provides:

1. **Multi-agent planning** - Guides LLMs to produce structured plans for complex fact-checking
2. **Stateful workflows** - Tracks progress through the fact-checking pipeline
3. **Authenticated tool calling** - Seamlessly integrates with search and other tools

The integration allows for a more robust fact-checking pipeline with better visibility into the LLM's reasoning process.

### Using Portia Integration

By default, the system now uses Portia for fact-checking. To switch between the original pipeline and Portia, modify the `use_portia` flag in `main.py`:

```python
# Choose which processing method to use
use_portia = True  # Set to False to use the original pipeline
```

### Required API Keys

To use the Portia integration, ensure you have the following API keys in your `.env` file:

```
GOOGLE_API_KEY=your_google_api_key
PORTIA_API_KEY=your_portia_api_key  # If using Portia cloud services
TAVILY_API_KEY=your_tavily_api_key  # For internet search
```

## Running the Application

### Running the Backend Server

To start the backend server:

1. Make sure you have activated your virtual environment
   ```
   # On Linux/Mac:
   source backend/portia-env-py311/bin/activate
   # On Windows:
   portia-env-py311\Scripts\activate
   ```

2. Navigate to the project root and run:
   ```
   python -m backend.run
   ```
   or
   ```
   cd backend
   python run.py
   ```

The backend server will start on `http://localhost:8002`.

### Running the Frontend

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install frontend dependencies (first time only):
   ```
   npm install
   # or
   yarn install
   ```

3. Start the development server:
   ```
   npm run dev
   # or
   yarn dev
   ```

The frontend will be available at `http://localhost:3000`.

### Accessing the Application

Once both backend and frontend are running:
1. Open your browser and go to `http://localhost:3000`
2. Enter your search query in the search bar
3. View the trustworthiness analysis of the search results

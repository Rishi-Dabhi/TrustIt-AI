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
   source portia-env-py311/bin/activate
   # On Windows:
   portia-env-py311\Scripts\activate
   ```

3. Install dependencies

   ```
   pip install portia-ai python-dotenv google-generativeai requests pydantic
   ```

4. Create a `.env` file in the project root with the following API keys:
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

### Command Line Interface

Run a search query from the command line:

```
python -m backend.cli "your search query here"
```

For example:

```
python -m backend.cli "who is the current UK prime minister"
```

### Importing as a Module

You can also use the search functionality in your own code:

```python
from backend.config import load_config
from backend.services import PortiaSearchService

# Load configuration and initialize service
config = load_config()
search_service = PortiaSearchService(config)

# Run a search
results = search_service.search("your search query")
print(results)
```

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

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

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

## Running the Backend Server

To start the backend server, run:

```
uvicorn backend.server:app --reload --host 0.0.0.0 --port 8002
```

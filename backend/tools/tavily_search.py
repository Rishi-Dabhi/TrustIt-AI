import requests
import logging
from pydantic import BaseModel, Field
from ..utils import tavily_limiter

# Set up logging
logger = logging.getLogger("tavily_search")

class TavilySearchArgs(BaseModel):
    """Input schema for Tavily search tool"""
    search_query: str = Field(
        description="The query to search for. For example, 'what is the capital of France?'"
    )

class TavilySearchTool:
    """Tavily search tool implementation for Portia"""
    
    def __init__(self, api_key):
        self.args_schema = TavilySearchArgs
        self.api_key = api_key
        self.id = "tavily_search"
        self.name = "Tavily Search"
        self.description = "Searches the internet using Tavily to find answers to the search query provided."
        self.output_schema = ("str", "str: output of the search results")
        self.should_summarize = True
        logger.info(f"TavilySearchTool initialized with rate limiter (delay={tavily_limiter.base_delay}s)")

    def run(self, args=None, **kwargs):
        """
        Run a search using Tavily's API.
        Accepts args object or kwargs that should contain 'search_query'
        """
        # Handle args parameter that Portia passes or fallback to kwargs
        if args and hasattr(args, 'search_query'):
            search_query = args.search_query
        else:
            search_query = kwargs.get("search_query", "")
            
        logger.info(f"Executing Tavily search for: '{search_query[:30]}...' (using rate limiter)")
        
        try:
            # Use the rate limiter to execute the search with retries and rate limiting
            logger.info(f"Calling tavily_limiter.execute_with_limit for '{search_query[:30]}...'")
            result = tavily_limiter.execute_with_limit(
                self._execute_search, 
                search_query
            )
            logger.info(f"tavily_limiter.execute_with_limit returned for '{search_query[:30]}...'")
            return result
        except Exception as e:
            error_message = f"Tavily search failed: {str(e)}"
            logger.error(f"Error in TavilySearchTool.run: {error_message}")
            return error_message
    
    def _execute_search(self, search_query):
        """Execute the actual search request to Tavily API"""
        logger.info(f"Executing direct Tavily API call for '{search_query[:30]}...'")
        url = "https://api.tavily.com/search"
        headers = {
            "content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "query": search_query,
            "search_depth": "basic",
            "include_answer": True,
            "include_images": False,
            "include_raw_content": False,
            "max_results": 5
        }
        
        logger.info(f"Sending request to Tavily API for '{search_query[:30]}...'")
        response = requests.post(url, json=payload, headers=headers)
        logger.info(f"Received response from Tavily API for '{search_query[:30]}...' with status {response.status_code}")
        response.raise_for_status()
        result = self._format_results(search_query, response.json())
        logger.info(f"Formatted results for '{search_query[:30]}...'")
        return result
    
    def _format_results(self, search_query, results):
        """Format the search results into a readable string"""
        formatted_results = f"Search query: {search_query}\n\n"
        
        if "answer" in results:
            formatted_results += f"Answer: {results['answer']}\n\n"
        
        if "results" in results:
            formatted_results += "Search results:\n"
            for i, result in enumerate(results["results"], 1):
                formatted_results += f"Result {i}:\n"
                formatted_results += f"Title: {result.get('title', 'No title')}\n"
                formatted_results += f"URL: {result.get('url', 'No URL')}\n"
                formatted_results += f"Content: {result.get('content', 'No content')[:300]}...\n\n"
        
        return formatted_results 
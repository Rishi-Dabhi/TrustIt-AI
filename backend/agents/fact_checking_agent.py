from typing import Dict, Any, List
import aiohttp
import json
from .base_agent import BaseAgent
import asyncio
# Import Tavily client
from tavily import TavilyClient

class FactCheckingAgent(BaseAgent):
    """Agent that verifies factual accuracy using external sources"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "fact_checking")
        # Get Tavily API key from config
        self.tavily_api_key = config.get("tavily_api_key")
        if not self.tavily_api_key:
            raise ValueError("Tavily API key not found in configuration.")
        # Initialize Tavily client
        self.tavily_client = TavilyClient(api_key=self.tavily_api_key)
        self.search_api_key = config.get("search_api_key")
        self.wiki_api_endpoint = "https://en.wikipedia.org/w/api.php"
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data through the fact checking pipeline"""
        print("--- [PROCESS] Entering process method ---")
        try:
            questions = input_data.get("questions", [])
            content = input_data.get("content", "")
            metadata = input_data.get("metadata", {})
            print(f"--- [PROCESS] Received {len(questions)} questions to process ---")

            fact_checks = []
            analysis_tasks = []
            questions_processed = [] # Keep track of questions corresponding to tasks

            print("--- [PROCESS] Starting loop to schedule analysis tasks ---")
            for question_dict in questions: # Now iterate over dicts
                print(f"--- [PROCESS] Scheduling analysis for question: {question_dict.get('question', 'N/A')[:30]}... ---")
                try:
                    question_text = question_dict.get("question", "")
                    if not question_text:
                        print("--- [PROCESS] Skipping empty question dict ---")
                        continue
                    # Schedule the analysis task, passing the full question dict
                    analysis_tasks.append(self._analyze_evidence(question_dict, content))
                    questions_processed.append(question_dict) # Store the original question dict
                except Exception as e:
                    # Handle immediate errors during task creation if any
                    print(f"--- [PROCESS] EXCEPTION during task scheduling for {question_dict.get('question', 'N/A')}: {e} ---")
                    fact_checks.append({
                        "question": question_dict,
                        "analysis": {
                            "verification_status": "error",
                            "confidence_score": 0.0,
                            "error": f"Error setting up analysis: {str(e)}"
                        }
                    })
            print("--- [PROCESS] Finished loop scheduling analysis tasks ---")

            # Run all analysis tasks concurrently
            if analysis_tasks:
                print(f"--- [PROCESS] Starting gather for {len(analysis_tasks)} analysis tasks ---")
                analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                print(f"--- [PROCESS] Finished gather for analysis tasks ---")

                # Process results
                print(f"--- [PROCESS] Processing {len(analysis_results)} results ---")
                for i, result in enumerate(analysis_results):
                    original_question = questions_processed[i]
                    if isinstance(result, Exception):
                        print(f"--- [PROCESS] EXCEPTION result from gather for {original_question.get('question', 'N/A')}: {result} ---")
                        fact_checks.append({
                            "question": original_question,
                            "analysis": {
                                "verification_status": "error",
                                "confidence_score": 0.0,
                                "error": str(result)
                            }
                        })
                    else:
                        fact_checks.append({
                            "question": original_question,
                            "analysis": result # Result is now the structured analysis dict
                        })
                print(f"--- [PROCESS] Finished processing results ---")
            else:
                print("--- [PROCESS] No analysis tasks were scheduled or ran ---")

            print("--- [PROCESS] Returning results ---")
            return {
                "fact_checks": fact_checks,
                "metadata": metadata
            }
            
        except Exception as e:
            print(f"--- [PROCESS] FATAL EXCEPTION in process method: {e} ---")
            return {
                "error": str(e),
                "fact_checks": []
            }
    
    async def _search_web(self, question_text: str) -> List[Dict[str, Any]]:
        """Search the web for evidence using Tavily API"""
        print(f"--- [TAVILY:{question_text[:20]}...] Entering _search_web ---")
        try:
            # Tavily client search is synchronous, run in thread pool
            loop = asyncio.get_running_loop()
            print(f"--- [TAVILY:{question_text[:20]}...] Calling run_in_executor ---")
            response = await loop.run_in_executor(
                None, # Default executor (ThreadPoolExecutor)
                lambda: self.tavily_client.search(
                    query=question_text,
                    search_depth="advanced", # Use advanced for more comprehensive results
                    max_results=5 # Limit results
                )
            )
            print(f"--- [TAVILY:{question_text[:20]}...] run_in_executor returned ---")
            # Extract relevant info from Tavily results
            results = response.get('results', [])
            processed_results = [{"url": r.get('url'), "content": r.get('content')} for r in results]
            print(f"--- [TAVILY:{question_text[:20]}...] Found {len(processed_results)} results ---")
            return processed_results
        except Exception as e:
            print(f"--- [TAVILY:{question_text[:20]}...] EXCEPTION in _search_web: {e} ---")
            return [] # Return empty list on error
    
    async def _search_wikipedia(self, question_text: str) -> List[Dict[str, Any]]:
        """Search Wikipedia for relevant information based on question text"""
        print(f"--- [WIKI:{question_text[:20]}...] Entering _search_wikipedia ---")
        async with aiohttp.ClientSession() as session:
            try:
                # Use question text for search terms
                search_terms = question_text

                # Search Wikipedia API
                params = {
                    "action": "query", "format": "json", "list": "search",
                    "srsearch": search_terms, "utf8": 1, "srlimit": 3
                }
                print(f"--- [WIKI:{question_text[:20]}...] Calling session.get with params: {params} ---")
                async with session.get(self.wiki_api_endpoint, params=params) as response:
                    print(f"--- [WIKI:{question_text[:20]}...] session.get returned status: {response.status} ---")
                    if response.status == 200:
                        print(f"--- [WIKI:{question_text[:20]}...] Reading response JSON ---")
                        data = await response.json()
                        print(f"--- [WIKI:{question_text[:20]}...] Processing results ---")
                        processed_results = self._process_wiki_results(data)
                        print(f"--- [WIKI:{question_text[:20]}...] Found {len(processed_results)} results ---")
                        return processed_results
                    else:
                        print(f"--- [WIKI:{question_text[:20]}...] API error status: {response.status} ---")
                        return []
                        
            except Exception as e:
                print(f"--- [WIKI:{question_text[:20]}...] EXCEPTION in _search_wikipedia: {e} ---")
                return []
    
    async def _analyze_evidence(self, question_dict: Dict[str, Any], content: str) -> Dict[str, Any]:
        """Analyze the evidence for a specific question using search results"""
        question_text = question_dict.get("question", "Unknown question")
        print(f"--- [ANALYZE:{question_text[:20]}...] Entering _analyze_evidence ---")
        try:
            # 1. Gather evidence concurrently
            print(f"--- [ANALYZE:{question_text[:20]}...] Starting gather for search tasks ---")
            web_search_task = self._search_web(question_text)
            wiki_search_task = self._search_wikipedia(question_text)
            web_results, wiki_results = await asyncio.gather(
                web_search_task, wiki_search_task, return_exceptions=True
            )
            print(f"--- [ANALYZE:{question_text[:20]}...] Finished gather for search tasks ---")

            # Handle potential errors from search tasks
            web_evidence_str = "No web results found or error during search."
            if isinstance(web_results, list):
                 web_evidence_str = "\n".join([f"- {r.get('content', 'N/A')} (Source: {r.get('url', 'N/A')})" for r in web_results])
            elif isinstance(web_results, Exception):
                 web_evidence_str = f"Error during web search: {web_results}"
                 print(f"--- [ANALYZE:{question_text[:20]}...] Web search resulted in error: {web_results} ---")

            wiki_evidence_str = "No Wikipedia results found or error during search."
            if isinstance(wiki_results, list) and wiki_results:
                 wiki_evidence_str = "\n".join([f"- {r.get('title', 'N/A')}: {r.get('snippet', 'N/A')}" for r in wiki_results])
            elif isinstance(wiki_results, Exception):
                 wiki_evidence_str = f"Error during Wikipedia search: {wiki_results}"
                 print(f"--- [ANALYZE:{question_text[:20]}...] Wiki search resulted in error: {wiki_results} ---")

            # 2. Create the analysis prompt including search evidence
            prompt = f"""Please perform a fact-checking assessment based *only* on the provided context and evidence.

Original Content:
{content}

Question to Verify:
{question_text}

Web Search Evidence:
{web_evidence_str}

Wikipedia Evidence:
{wiki_evidence_str}

Instructions:
Analyze the evidence gathered above to answer the 'Question to Verify' in relation to the 'Original Content'.
Provide:
1. Verification status (e.g., True, False, Partially True, Unclear due to conflicting evidence, Cannot Verify)
2. Confidence score (0.0 to 1.0) representing your certainty in the verification status based *only* on the provided evidence.
3. Supporting evidence (List specific points from the web/Wikipedia evidence that support the status).
4. Contradicting evidence (List specific points from the web/Wikipedia evidence that contradict the status).
5. Reasoning (Explain your assessment step-by-step, referencing the evidence).
6. Evidence gaps (Mention any missing information needed for a more certain assessment).
7. Recommendations (Suggest further checks if needed).

Respond *only* with the structured analysis, using the headings above."""

            # 3. Get the model's response
            if not hasattr(self, 'model') or self.model is None:
                 print(f"--- [ANALYZE:{question_text[:20]}...] ERROR: Generative model not initialized. ---")
                 raise ValueError("Generative model not available for analysis.")

            print(f"--- [ANALYZE:{question_text[:20]}...] Calling LLM.generate_content ---")
            response = self.model.generate_content(prompt)
            print(f"--- [ANALYZE:{question_text[:20]}...] LLM.generate_content returned ---")

            # 4. Parse the response
            print(f"--- [ANALYZE:{question_text[:20]}...] Parsing LLM response ---")
            if response.text:
                parsed_analysis = self._parse_analysis(response.text)
                # Add sources based on successful searches
                sources = []
                if isinstance(web_results, list) and web_results:
                    sources.extend([r.get('url', 'Tavily') for r in web_results if r.get('url')])
                if isinstance(wiki_results, list) and wiki_results:
                     sources.append("Wikipedia")
                if not sources:
                    sources.append("LLM Analysis based on content")

                parsed_analysis["sources"] = list(set(sources)) # Unique sources
                print(f"--- [ANALYZE:{question_text[:20]}...] Finished analysis ---")
                return parsed_analysis
            else:
                 print(f"--- [ANALYZE:{question_text[:20]}...] LLM response empty ---")
                 # Return error structure matching parsed format
                 return {
                     "verification_status": "error", "confidence_score": 0.0,
                     "supporting_evidence": [], "contradicting_evidence": [],
                     "reasoning": "Failed to get analysis from LLM", "evidence_gaps": [],
                     "recommendations": [], "sources": []
                 }

        except Exception as e:
            print(f"--- [ANALYZE:{question_text[:20]}...] EXCEPTION in _analyze_evidence: {e} ---")
            # Return error structure matching parsed format
            return {
                 "verification_status": "error", "confidence_score": 0.0,
                 "supporting_evidence": [], "contradicting_evidence": [],
                 "reasoning": f"Error during analysis: {str(e)}", "evidence_gaps": [],
                 "recommendations": [], "sources": []
            }
    
    def _process_search_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """(Deprecated/Not Used - Tavily processing is inline in _search_web)"""
        # Implement based on your search API response structure if not using Tavily directly
        return []
    
    def _process_wiki_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process and structure Wikipedia results"""
        results = []
        try:
            for item in data.get("query", {}).get("search", []):
                results.append({
                    "title": item.get("title"),
                    # Clean snippet from HTML tags (simple approach)
                    "snippet": item.get("snippet", "").replace('<span class="searchmatch">', '').replace('</span>', ''),
                    "pageid": item.get("pageid")
                })
        except Exception as e:
            print(f"Error processing Wikipedia results: {e}")
        return results
    
    def _parse_analysis(self, text: str) -> Dict[str, Any]:
        """Parse the model's analysis response based on expected headings"""
        analysis = {
            "verification_status": "Unknown",
            "confidence_score": 0.0,
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "reasoning": "",
            "evidence_gaps": [],
            "recommendations": [],
            "sources": [] # Sources will be added in _analyze_evidence
        }
        current_section = None
        buffer = []

        lines = text.split("\n")
        for i, line in enumerate(lines):
            line_strip = line.strip()
            if not line_strip and not buffer: # Skip empty lines between sections
                 continue

            # Detect headers (case-insensitive)
            lower_line = line_strip.lower()
            new_section = None
            if lower_line.startswith("1. verification status:") or lower_line.startswith("verification status:"):
                new_section = "verification_status"
                buffer = [line_strip.split(":", 1)[-1].strip()]
            elif lower_line.startswith("2. confidence score:") or lower_line.startswith("confidence score:"):
                 new_section = "confidence_score"
                 buffer = [line_strip.split(":", 1)[-1].strip()]
            elif lower_line.startswith("3. supporting evidence:") or lower_line.startswith("supporting evidence:"):
                new_section = "supporting_evidence"
                buffer = [line_strip.split(":", 1)[-1].strip()] # Capture rest of line if any
            elif lower_line.startswith("4. contradicting evidence:") or lower_line.startswith("contradicting evidence:"):
                new_section = "contradicting_evidence"
                buffer = [line_strip.split(":", 1)[-1].strip()]
            elif lower_line.startswith("5. reasoning:") or lower_line.startswith("reasoning:"):
                new_section = "reasoning"
                buffer = [line_strip.split(":", 1)[-1].strip()]
            elif lower_line.startswith("6. evidence gaps:") or lower_line.startswith("evidence gaps:"):
                 new_section = "evidence_gaps"
                 buffer = [line_strip.split(":", 1)[-1].strip()]
            elif lower_line.startswith("7. recommendations:") or lower_line.startswith("recommendations:"):
                 new_section = "recommendations"
                 buffer = [line_strip.split(":", 1)[-1].strip()]

            # If new section detected, process buffer for previous section
            if new_section:
                if current_section:
                    section_content = "\n".join(filter(None, buffer)).strip() # Join non-empty lines
                    if current_section == "confidence_score":
                        try:
                            score = float(section_content)
                            analysis[current_section] = min(max(score, 0.0), 1.0)
                        except ValueError:
                            print(f"Warning: Could not parse confidence score: {section_content}")
                            analysis[current_section] = 0.0 # Default on parse error
                    elif current_section in ["supporting_evidence", "contradicting_evidence", "evidence_gaps", "recommendations"]:
                         # Split list items, handle simple bullet points or numbered lists
                         items = [item.strip() for item in section_content.split('\n') if item.strip()]
                         analysis[current_section] = [item.lstrip('-* 0123456789.').strip() for item in items] # Remove common list markers
                    else: # verification_status, reasoning
                        analysis[current_section] = section_content
                current_section = new_section
                buffer = [buffer[0].strip()] # Start buffer with content after colon
            elif current_section:
                # Continue adding to buffer for the current section
                buffer.append(line_strip)


        # Process the buffer for the last section
        if current_section:
            section_content = "\n".join(filter(None, buffer)).strip()
            if current_section == "confidence_score":
                 try:
                     score = float(section_content)
                     analysis[current_section] = min(max(score, 0.0), 1.0)
                 except ValueError:
                     print(f"Warning: Could not parse confidence score: {section_content}")
                     analysis[current_section] = 0.0
            elif current_section in ["supporting_evidence", "contradicting_evidence", "evidence_gaps", "recommendations"]:
                  items = [item.strip() for item in section_content.split('\n') if item.strip()]
                  analysis[current_section] = [item.lstrip('-* 0123456789.').strip() for item in items]
            else:
                 analysis[current_section] = section_content

        # Handle cases where the LLM might not follow instructions perfectly
        if analysis["verification_status"] == "Unknown" and analysis["reasoning"]:
             analysis["verification_status"] = "See Reasoning"


        return analysis 
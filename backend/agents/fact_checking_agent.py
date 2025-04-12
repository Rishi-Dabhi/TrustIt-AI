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

            # Create a summary from the evidence for easier analysis
            evidence_summary = "Evidence Summary:\n"
            
            # First analyze web evidence
            if isinstance(web_results, list) and web_results:
                for i, result in enumerate(web_results[:3]):  # Focus on top 3 results
                    content = result.get('content', '').strip()
                    url = result.get('url', 'Unknown source')
                    if content:
                        evidence_summary += f"\nWeb Source #{i+1} ({url}):\n"
                        evidence_summary += f"{content[:500]}...\n" if len(content) > 500 else f"{content}\n"
                        evidence_summary += f"Key points: \n"
                        # Extract 2-3 key points from this source
                        evidence_summary += f"- The source discusses {question_text.lower()} with relevant information.\n"
            
            # Then analyze Wikipedia evidence
            if isinstance(wiki_results, list) and wiki_results:
                evidence_summary += "\nWikipedia Evidence:\n"
                for i, result in enumerate(wiki_results[:2]):  # Focus on top 2 results
                    title = result.get('title', 'Unknown topic')
                    snippet = result.get('snippet', '').strip()
                    if snippet:
                        evidence_summary += f"- {title}: {snippet}\n"

            # 2. Create the analysis prompt including search evidence
            prompt = f"""You are an expert fact-checker. Your task is to determine whether the evidence provided supports, contradicts, or is insufficient to verify the claim in question.

Original Content to Check:
{content}

Specific Claim/Question to Verify:
{question_text}

{evidence_summary}

Full Web Search Evidence:
{web_evidence_str}

Full Wikipedia Evidence:
{wiki_evidence_str}

Instructions:
1. Carefully analyze the claim against the evidence.
2. Focus on factual accuracy only, not opinions or subjective interpretations.
3. Your task is to determine if the evidence directly addresses and verifies/refutes the claim.

Provide your analysis in the following structured format:

1. Verification Status: Choose ONE of these options:
   - "Verified" - Evidence clearly confirms the claim
   - "False" - Evidence clearly contradicts the claim
   - "Partially True" - Evidence confirms some aspects but not others
   - "Misleading" - Claim has some truth but presents information in a way that could lead to incorrect conclusions
   - "Unsubstantiated" - Claim makes assertions that go beyond available evidence
   - "Unable to Verify" - Insufficient or unclear evidence to make a determination

2. Confidence Score: Provide a score from 0.0 to 1.0 indicating your confidence in this verification status.

3. Supporting Evidence: List specific points from the search results that support the claim.

4. Contradicting Evidence: List specific points from the search results that contradict the claim.

5. Reasoning: Explain your verification decision, outlining how you weighed the evidence.

6. Evidence Gaps: Note any missing information that would help verify the claim more conclusively.

7. Recommendations: Suggest additional fact-checking steps if needed.

Answer ONLY with the structured analysis exactly as outlined above, with numbered headings.
"""

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
                # Log the verification status to help with debugging
                status = parsed_analysis.get("verification_status", "Unknown")
                print(f"--- [ANALYZE:{question_text[:20]}...] Verification Status: {status} ---")
                
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
                     "verification_status": "Unable to Verify", "confidence_score": 0.0,
                     "supporting_evidence": [], "contradicting_evidence": [],
                     "reasoning": "Failed to get analysis from LLM", "evidence_gaps": [],
                     "recommendations": [], "sources": []
                 }

        except Exception as e:
            print(f"--- [ANALYZE:{question_text[:20]}...] EXCEPTION in _analyze_evidence: {e} ---")
            # Return error structure matching parsed format
            return {
                 "verification_status": "Error", "confidence_score": 0.0,
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
            
            # Improved section detection with more robust patterns
            if any(pattern in lower_line for pattern in ["1. verification status", "verification status:"]):
                new_section = "verification_status"
                # Extract status value after the colon
                status_value = line_strip.split(":", 1)[-1].strip() if ":" in line_strip else ""
                buffer = [status_value]
            elif any(pattern in lower_line for pattern in ["2. confidence score", "confidence score:"]):
                new_section = "confidence_score" 
                score_value = line_strip.split(":", 1)[-1].strip() if ":" in line_strip else ""
                buffer = [score_value]
            elif any(pattern in lower_line for pattern in ["3. supporting evidence", "supporting evidence:"]):
                new_section = "supporting_evidence"
                evidence_value = line_strip.split(":", 1)[-1].strip() if ":" in line_strip else ""
                buffer = [evidence_value]
            elif any(pattern in lower_line for pattern in ["4. contradicting evidence", "contradicting evidence:"]):
                new_section = "contradicting_evidence"
                evidence_value = line_strip.split(":", 1)[-1].strip() if ":" in line_strip else ""
                buffer = [evidence_value]
            elif any(pattern in lower_line for pattern in ["5. reasoning", "reasoning:"]):
                new_section = "reasoning"
                reasoning_value = line_strip.split(":", 1)[-1].strip() if ":" in line_strip else ""
                buffer = [reasoning_value]
            elif any(pattern in lower_line for pattern in ["6. evidence gaps", "evidence gaps:"]):
                new_section = "evidence_gaps"
                gaps_value = line_strip.split(":", 1)[-1].strip() if ":" in line_strip else ""
                buffer = [gaps_value]
            elif any(pattern in lower_line for pattern in ["7. recommendations", "recommendations:"]):
                new_section = "recommendations"
                rec_value = line_strip.split(":", 1)[-1].strip() if ":" in line_strip else ""
                buffer = [rec_value]

            # If new section detected, process buffer for previous section
            if new_section:
                # Process previous section if any
                if current_section:
                    section_content = "\n".join(filter(None, buffer)).strip() # Join non-empty lines
                    if current_section == "confidence_score":
                        try:
                            # Extract numeric value using regex to handle various formats
                            import re
                            number_match = re.search(r'(\d+(?:\.\d+)?)', section_content)
                            if number_match:
                                score = float(number_match.group(1))
                                analysis[current_section] = min(max(score, 0.0), 1.0)
                            else:
                                print(f"Warning: Could not parse confidence score: {section_content}")
                                analysis[current_section] = 0.5  # Default to middle value on parse error
                        except ValueError:
                            print(f"Warning: Could not parse confidence score: {section_content}")
                            analysis[current_section] = 0.5  # Default to middle value on parse error
                    elif current_section == "verification_status":
                        # Standardize verification status
                        status_lower = section_content.lower()
                        # First check if the status contains a numeric value (e.g., "0.9")
                        import re
                        numeric_match = re.search(r'(\d+(?:\.\d+)?)', status_lower)
                        if numeric_match:
                            # If it's a numeric value, clean it up and convert status based on the value
                            numeric_value = float(numeric_match.group(1))
                            if numeric_value >= 0.8:
                                analysis[current_section] = "Verified"
                            elif numeric_value >= 0.6:
                                analysis[current_section] = "Partially True"
                            elif numeric_value >= 0.4:
                                analysis[current_section] = "Unable to Verify"
                            elif numeric_value >= 0.2:
                                analysis[current_section] = "Misleading"
                            else:
                                analysis[current_section] = "False"
                            # Also set the confidence score if it hasn't been set yet
                            if analysis["confidence_score"] == 0.0:
                                analysis["confidence_score"] = numeric_value
                        elif "verified" in status_lower or "true" in status_lower or "confirm" in status_lower:
                            analysis[current_section] = "Verified"
                        elif "false" in status_lower or "incorrect" in status_lower or "untrue" in status_lower:
                            analysis[current_section] = "False"
                        elif "partially" in status_lower or "partly" in status_lower:
                            analysis[current_section] = "Partially True"
                        elif "misleading" in status_lower:
                            analysis[current_section] = "Misleading"
                        elif "unsubstantiated" in status_lower or "unsupported" in status_lower:
                            analysis[current_section] = "Unsubstantiated"
                        elif "unable" in status_lower or "insufficient" in status_lower or "unclear" in status_lower:
                            analysis[current_section] = "Unable to Verify"
                        else:
                            analysis[current_section] = section_content.capitalize()
                    elif current_section in ["supporting_evidence", "contradicting_evidence", "evidence_gaps", "recommendations"]:
                         # Split list items, handle simple bullet points or numbered lists
                         items = []
                         for item in section_content.split('\n'):
                             item = item.strip()
                             if item:
                                 # Clean up bullet points and numbering
                                 cleaned_item = re.sub(r'^[-•*]|\d+[\.)]|\s-\s', '', item).strip()
                                 if cleaned_item:
                                     items.append(cleaned_item)
                         analysis[current_section] = items
                    else: # reasoning
                        analysis[current_section] = section_content
                
                # Set new section
                current_section = new_section
                # buffer already set during section detection
            elif current_section:
                # Continue adding to buffer for the current section
                buffer.append(line_strip)

        # Process the buffer for the last section
        if current_section:
            section_content = "\n".join(filter(None, buffer)).strip()
            if current_section == "confidence_score":
                try:
                    # Extract numeric value using regex
                    import re
                    number_match = re.search(r'(\d+(?:\.\d+)?)', section_content)
                    if number_match:
                        score = float(number_match.group(1))
                        analysis[current_section] = min(max(score, 0.0), 1.0)
                    else:
                        analysis[current_section] = 0.5  # Default to middle value
                except ValueError:
                    analysis[current_section] = 0.5  # Default to middle value
            elif current_section == "verification_status":
                # Standardize verification status
                status_lower = section_content.lower()
                # First check if the status contains a numeric value
                import re
                numeric_match = re.search(r'(\d+(?:\.\d+)?)', status_lower)
                if numeric_match:
                    # If it's a numeric value, clean it up and convert status based on the value
                    numeric_value = float(numeric_match.group(1))
                    if numeric_value >= 0.8:
                        analysis[current_section] = "Verified"
                    elif numeric_value >= 0.6:
                        analysis[current_section] = "Partially True"
                    elif numeric_value >= 0.4:
                        analysis[current_section] = "Unable to Verify"
                    elif numeric_value >= 0.2:
                        analysis[current_section] = "Misleading"
                    else:
                        analysis[current_section] = "False"
                    # Also set the confidence score if it hasn't been set yet
                    if analysis["confidence_score"] == 0.0:
                        analysis["confidence_score"] = numeric_value
                elif "verified" in status_lower or "true" in status_lower or "confirm" in status_lower:
                    analysis[current_section] = "Verified"
                elif "false" in status_lower or "incorrect" in status_lower or "untrue" in status_lower:
                    analysis[current_section] = "False"
                elif "partially" in status_lower or "partly" in status_lower:
                    analysis[current_section] = "Partially True"
                elif "misleading" in status_lower:
                    analysis[current_section] = "Misleading"
                elif "unsubstantiated" in status_lower or "unsupported" in status_lower:
                    analysis[current_section] = "Unsubstantiated"
                elif "unable" in status_lower or "insufficient" in status_lower or "unclear" in status_lower:
                    analysis[current_section] = "Unable to Verify"
                else:
                    analysis[current_section] = section_content.capitalize()
            elif current_section in ["supporting_evidence", "contradicting_evidence", "evidence_gaps", "recommendations"]:
                 # Split list items
                 items = []
                 for item in section_content.split('\n'):
                     item = item.strip()
                     if item:
                         # Clean up bullet points and numbering
                         import re
                         cleaned_item = re.sub(r'^[-•*]|\d+[\.)]|\s-\s', '', item).strip()
                         if cleaned_item:
                             items.append(cleaned_item)
                 analysis[current_section] = items
            else: # reasoning
                analysis[current_section] = section_content

        # Make sure all sections are properly filled
        if not analysis["verification_status"] or analysis["verification_status"] == "Unknown":
            # Try to infer from reasoning if present
            if analysis["reasoning"]:
                reasoning_lower = analysis["reasoning"].lower()
                if "verified" in reasoning_lower or "true" in reasoning_lower or "confirmed" in reasoning_lower:
                    analysis["verification_status"] = "Verified"
                elif "false" in reasoning_lower or "incorrect" in reasoning_lower or "untrue" in reasoning_lower:
                    analysis["verification_status"] = "False"
                elif "partially" in reasoning_lower or "partly" in reasoning_lower:
                    analysis["verification_status"] = "Partially True"
                elif "misleading" in reasoning_lower:
                    analysis["verification_status"] = "Misleading"
                elif "unsubstantiated" in reasoning_lower or "unsupported" in reasoning_lower:
                    analysis["verification_status"] = "Unsubstantiated"
                elif "unable" in reasoning_lower or "insufficient" in reasoning_lower or "unclear" in reasoning_lower:
                    analysis["verification_status"] = "Unable to Verify"
                else:
                    analysis["verification_status"] = "Unable to Verify"  # Default if can't infer
            else:
                analysis["verification_status"] = "Unable to Verify"  # Default if no reasoning

        # Calculate confidence score based on supporting and contradicting evidence
        if analysis["confidence_score"] == 0.0 or analysis["confidence_score"] == 0.5:
            supporting_count = len(analysis["supporting_evidence"])
            contradicting_count = len(analysis["contradicting_evidence"])
            total_evidence = supporting_count + contradicting_count
            
            # If we have evidence, calculate confidence based on the proportion of supporting evidence
            if total_evidence > 0:
                evidence_ratio = supporting_count / total_evidence
                # Adjust ratio to avoid 0 or 1.0 confidence
                evidence_ratio = max(0.1, min(0.9, evidence_ratio))
                
                # Use the evidence ratio as confidence if verification status indicates support or contradiction
                status = analysis["verification_status"].lower()
                if any(term in status for term in ["verified", "true", "partially", "confirmed"]):
                    analysis["confidence_score"] = max(0.6, evidence_ratio)
                elif any(term in status for term in ["false", "incorrect", "mislead"]):
                    analysis["confidence_score"] = max(0.6, 1 - evidence_ratio)
                else:
                    # For uncertain statuses, use a confidence reflecting the uncertainty
                    analysis["confidence_score"] = 0.5
            else:
                # If no specific evidence points, use a moderate confidence based on status
                status = analysis["verification_status"].lower()
                if any(term in status for term in ["verified", "true", "confirmed"]):
                    analysis["confidence_score"] = 0.8
                elif any(term in status for term in ["false", "incorrect"]):
                    analysis["confidence_score"] = 0.8
                elif any(term in status for term in ["partially", "mislead"]):
                    analysis["confidence_score"] = 0.6
                else:
                    analysis["confidence_score"] = 0.5

        # Print the final parsed analysis for debugging
        print(f"--- [PARSE] Final verification_status: {analysis['verification_status']}")
        print(f"--- [PARSE] Final confidence_score: {analysis['confidence_score']}")
        
        return analysis 
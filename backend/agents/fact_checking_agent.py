from typing import Dict, Any, List
import aiohttp
import json
from .base_agent import BaseAgent
import asyncio
# Import Tavily client
from tavily import TavilyClient
import re
import traceback
# Use relative imports
from ..utils import tavily_limiter, gemini_limiter

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

            print("--- [PROCESS] Starting sequential processing of questions ---")
            for i, question_dict in enumerate(questions):
                print(f"--- [PROCESS] Processing question {i+1}/{len(questions)}: {question_dict.get('question', 'N/A')[:30]}... ---")
                try:
                    question_text = question_dict.get("question", "")
                    if not question_text:
                        print("--- [PROCESS] Skipping empty question dict ---")
                        continue
                    
                    # Process each question sequentially to respect rate limits
                    try:
                        analysis_result = await self._analyze_evidence(question_dict, content)
                        fact_checks.append({
                            "question": question_dict,
                            "analysis": analysis_result
                        })
                        
                        # Add a mandatory pause between questions to ensure rate limits are respected
                        if i < len(questions) - 1:  # Don't wait after the last question
                            wait_time = 5.0  # 5 second pause between questions
                            print(f"--- [PROCESS] Waiting {wait_time}s before processing next question ---")
                            await asyncio.sleep(wait_time)
                            
                    except Exception as e:
                        print(f"--- [PROCESS] Error analyzing evidence: {str(e)} ---")
                        fact_checks.append({
                            "question": question_dict,
                            "analysis": {
                                "verification_status": "error",
                                "confidence_score": 0.0,
                                "error": f"Error during analysis: {str(e)}",
                                "supporting_evidence": [],
                                "contradicting_evidence": [],
                                "reasoning": f"Analysis failed: {str(e)}",
                                "evidence_gaps": [],
                                "recommendations": [],
                                "sources": [],
                                "source_evaluations": []
                            }
                        })
                except Exception as e:
                    # Handle immediate errors during task creation if any
                    print(f"--- [PROCESS] EXCEPTION during processing for {question_dict.get('question', 'N/A')}: {e} ---")
                    fact_checks.append({
                        "question": question_dict,
                        "analysis": {
                            "verification_status": "error",
                            "confidence_score": 0.0,
                            "error": f"Error setting up analysis: {str(e)}",
                            "supporting_evidence": [],
                            "contradicting_evidence": [],
                            "reasoning": f"Failed to process: {str(e)}",
                            "evidence_gaps": [],
                            "recommendations": [],
                            "sources": [],
                            "source_evaluations": []
                        }
                    })
            print("--- [PROCESS] Finished processing all questions ---")

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
            # Tavily client search is synchronous, run in thread pool with rate limiting
            loop = asyncio.get_running_loop()
            print(f"--- [TAVILY:{question_text[:20]}...] Calling run_in_executor with rate limiting ---")
            response = await loop.run_in_executor(
                None, # Default executor (ThreadPoolExecutor)
                lambda: tavily_limiter.execute_with_limit(
                    self.tavily_client.search,
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
            # 1. Gather evidence sequentially to respect rate limits
            print(f"--- [ANALYZE:{question_text[:20]}...] Starting sequential search tasks ---")
            
            # Execute web search first
            print(f"--- [ANALYZE:{question_text[:20]}...] Starting web search ---")
            try:
                web_results = await self._search_web(question_text)
                web_error = None
            except Exception as e:
                web_results = []
                web_error = e
                print(f"--- [ANALYZE:{question_text[:20]}...] Web search resulted in error: {e} ---")
            
            # Then execute Wikipedia search
            print(f"--- [ANALYZE:{question_text[:20]}...] Starting Wikipedia search ---")
            try:
                wiki_results = await self._search_wikipedia(question_text)
                wiki_error = None
            except Exception as e:
                wiki_results = []
                wiki_error = e
                print(f"--- [ANALYZE:{question_text[:20]}...] Wiki search resulted in error: {e} ---")
            
            print(f"--- [ANALYZE:{question_text[:20]}...] Finished sequential search tasks ---")

            # Handle potential errors from search tasks
            web_evidence_str = "No web results found or error during search."
            if isinstance(web_results, list):
                 web_evidence_str = "\n".join([f"- {r.get('content', 'N/A')} (Source: {r.get('url', 'N/A')})" for r in web_results])
            elif web_error:
                 web_evidence_str = f"Error during web search: {web_error}"
                 print(f"--- [ANALYZE:{question_text[:20]}...] Web search resulted in error: {web_error} ---")

            wiki_evidence_str = "No Wikipedia results found or error during search."
            if isinstance(wiki_results, list) and wiki_results:
                 wiki_evidence_str = "\n".join([f"- {r.get('title', 'N/A')}: {r.get('snippet', 'N/A')}" for r in wiki_results])
            elif wiki_error:
                 wiki_evidence_str = f"Error during Wikipedia search: {wiki_error}"
                 print(f"--- [ANALYZE:{question_text[:20]}...] Wiki search resulted in error: {wiki_error} ---")

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

            # 2. Create the analysis prompt including search evidence with improved instructions
            prompt = f"""You are an expert fact-checker tasked with determining the accuracy of claims based on evidence. Your goal is to provide a clear, well-reasoned verification that weighs all available evidence.

Original Content to Check:
{content}

Specific Claim/Question to Verify:
{question_text}

{evidence_summary}

Full Web Search Evidence:
{web_evidence_str}

Full Wikipedia Evidence:
{wiki_evidence_str}

INSTRUCTIONS FOR ANALYSIS:
1. First, identify the specific factual assertions in the claim that need verification.
2. Carefully evaluate each piece of evidence for its relevance, credibility, and relationship to the claim.
3. Focus on factual accuracy only, not opinions or subjective interpretations.
4. For EACH source, determine if it SUPPORTS (YES) or CONTRADICTS (NO) the claim.
5. Be precise about what parts of a claim can and cannot be verified with the available evidence.
6. Use neutral language and avoid inferring information not supported by the evidence.

===== FORMAT YOUR ANALYSIS EXACTLY AS FOLLOWS =====

1. Verification Status: Choose ONE of these options ONLY:
   - "Verified" - Evidence clearly confirms the claim with high confidence
   - "False" - Evidence clearly contradicts the claim with high confidence
   - "Partially True" - Evidence confirms some aspects but contradicts or fails to support others
   - "Misleading" - Claim has factual elements but presents them in a way that creates a false impression
   - "Unsubstantiated" - Claim makes assertions that cannot be supported by the available evidence
   - "Unable to Verify" - Insufficient or unclear evidence to make a determination

2. Source Evaluation:
   - For each source that provides relevant information, list the source and whether it SUPPORTS (YES) or CONTRADICTS (NO) the claim.
   - IMPORTANT: YES means the source supports the claim as stated. NO means the source contradicts the claim.
   - For "evidence-seeking" questions (like "What evidence exists for X?"):
     - YES means the source provides evidence that X exists
     - NO means the source indicates no evidence for X exists
   - For example, if the claim is "Donald Trump was involved in 9/11" and a source shows he wasn't:
     - You would mark that as NO because the source contradicts the claim
   - Format: Source URL or name: YES/NO - Brief justification
   - Example: 
     - example.com/article: YES - Directly confirms the statistics cited in the claim
     - Wikipedia: NO - Contains contradicting information about the timeline

3. Supporting Evidence: List specific facts from the search results that directly support the claim.
   - Include only direct evidence that confirms specific aspects of the claim
   - Cite the source for each piece of evidence
   - Do not include speculative or tangential information

4. Contradicting Evidence: List specific facts from the search results that directly contradict the claim.
   - Include only direct evidence that challenges specific aspects of the claim
   - Cite the source for each piece of evidence
   - Do not include speculative or tangential information

5. Reasoning: Provide a step-by-step analysis explaining how you evaluated the evidence and reached your conclusion.
   - Explicitly connect evidence to specific parts of the claim
   - Explain how you weighed conflicting evidence
   - Clarify why some evidence was considered more credible or relevant
   - Identify logical inferences made and their justification

6. Evidence Gaps: Note specific missing information that would strengthen the verification.
   - Identify key aspects of the claim that lack sufficient evidence
   - Note what specific additional information would improve the analysis

7. Recommendations: Suggest specific, actionable steps to better verify this claim.
   - Recommend particular sources, experts, or data that could provide additional clarity
   - Suggest alternative phrasings that would make the claim more accurate

Answer ONLY with the structured analysis exactly as outlined above, with numbered headings.
"""

            # 3. Get the model's response
            if not hasattr(self, 'model') or self.model is None:
                 print(f"--- [ANALYZE:{question_text[:20]}...] ERROR: Generative model not initialized. ---")
                 raise ValueError("Generative model not available for analysis.")

            print(f"--- [ANALYZE:{question_text[:20]}...] Calling LLM.generate_content ---")
            try:
                # Use gemini_limiter to handle rate limiting and retries
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,  # Default executor
                    lambda: gemini_limiter.execute_with_limit(
                        self.model.generate_content,
                        prompt
                    )
                )
                print(f"--- [ANALYZE:{question_text[:20]}...] LLM.generate_content returned ---")
            except Exception as e:
                print(f"--- [ANALYZE:{question_text[:20]}...] Error calling LLM: {str(e)} ---")
                raise ValueError(f"Failed to get LLM response: {str(e)}")

            # 4. Parse the response
            print(f"--- [ANALYZE:{question_text[:20]}...] Parsing LLM response ---")
            if response.text:
                parsed_analysis = self._parse_analysis(response.text, question_text)
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

                # Ensure confidence_score is a float - this fixes the toFixed() error in the frontend
                if "confidence_score" in parsed_analysis:
                    try:
                        parsed_analysis["confidence_score"] = float(parsed_analysis["confidence_score"])
                    except (ValueError, TypeError):
                        parsed_analysis["confidence_score"] = 0.5  # Default to 0.5 if conversion fails
                
                parsed_analysis["sources"] = list(set(sources)) # Unique sources
                
                # Print source evaluations and confidence score for debugging
                source_evaluations = parsed_analysis.get("source_evaluations", [])
                if source_evaluations:
                    print(f"--- [ANALYZE:{question_text[:20]}...] Source Evaluations:")
                    for eval in source_evaluations:
                        print(f"  - {eval['source']}: {eval['verdict']} - {eval['reason'][:50]}...")
                
                print(f"--- [ANALYZE:{question_text[:20]}...] Finished analysis with confidence score: {parsed_analysis.get('confidence_score')} ---")
                return parsed_analysis
            else:
                 print(f"--- [ANALYZE:{question_text[:20]}...] LLM response empty ---")
                 # Return error structure matching parsed format
                 return {
                     "verification_status": "Unable to Verify", "confidence_score": 0.5,  # Use float for confidence_score
                     "supporting_evidence": [], "contradicting_evidence": [],
                     "reasoning": "Failed to get analysis from LLM", "evidence_gaps": [],
                     "recommendations": [], "sources": [], "source_evaluations": []
                 }

        except Exception as e:
            print(f"--- [ANALYZE:{question_text[:20]}...] EXCEPTION in _analyze_evidence: {e} ---")
            # Return error structure matching parsed format
            return {
                 "verification_status": "Error", "confidence_score": 0.0,
                 "supporting_evidence": [], "contradicting_evidence": [],
                 "reasoning": f"Error during analysis: {str(e)}", "evidence_gaps": [],
                 "recommendations": [], "sources": [], "source_evaluations": []
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
    
    def _parse_analysis(self, text: str, question_text: str = "") -> Dict[str, Any]:
        """Parse the model's analysis response with improved accuracy for verification status and reasoning"""
        analysis = {
            "verification_status": "Unknown",
            "confidence_score": 0.5,  # Default to 0.5 instead of 0.0
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "reasoning": "",
            "evidence_gaps": [],
            "recommendations": [],
            "sources": [], # Sources will be added in _analyze_evidence
            "source_evaluations": []  # Track individual source evaluations
        }
        current_section = None
        buffer = []

        # First, extract specific verification status using regex for better precision
        import re
        
        # Try to find the verification status section with its value
        verification_pattern = re.search(r'(?:1\.|[Vv]erification\s*[Ss]tatus:?)\s*(?:")?([^"\n.]+)(?:")?', text)
        if verification_pattern:
            raw_status = verification_pattern.group(1).strip()
            # Map status to standardized values
            status_mapping = {
                'verified': "Verified",
                'true': "Verified",
                'confirm': "Verified",
                'false': "False", 
                'incorrect': "False",
                'untrue': "False",
                'partially true': "Partially True",
                'partially': "Partially True",
                'partly': "Partially True",
                'misleading': "Misleading",
                'unsubstantiated': "Unsubstantiated",
                'unsupported': "Unsubstantiated",
                'unable to verify': "Unable to Verify",
                'insufficient': "Unable to Verify",
                'unclear': "Unable to Verify"
            }
            
            # Find matching status
            status_lower = raw_status.lower()
            matched = False
            for key, value in status_mapping.items():
                if key in status_lower:
                    analysis["verification_status"] = value
                    matched = True
                    break
            
            # If no match found, use the raw status with first letter capitalized
            if not matched:
                analysis["verification_status"] = raw_status.capitalize()
        
        # Extract source evaluations and count YES/NO responses
        source_eval_section = re.search(r'(?:2\.|[Ss]ource\s*[Ee]valuation:?)(.*?)(?:3\.|[Ss]upporting\s*[Ee]vidence:?)', text, re.DOTALL)
        yes_count = 0
        no_count = 0
        
        if source_eval_section:
            source_lines = source_eval_section.group(1).strip().split('\n')
            for line in source_lines:
                line = line.strip()
                if not line or line.startswith('-') and len(line) < 3:  # Skip empty lines or just bullet points
                    continue
                    
                # Extract source evaluations using regex
                source_match = re.search(r'[-•*]?\s*(.*?):\s*(YES|NO|yes|no|Yes|No)\s*-\s*(.*)', line)
                if source_match:
                    source = source_match.group(1).strip()
                    verdict = source_match.group(2).upper()
                    reason = source_match.group(3).strip()
                    
                    analysis["source_evaluations"].append({
                        "source": source,
                        "verdict": verdict,
                        "reason": reason
                    })
                    
                    if verdict == "YES":
                        yes_count += 1
                    elif verdict == "NO":
                        no_count += 1
        
        # Calculate confidence score based on proportion of YES/NO responses
        total_sources = yes_count + no_count
        if total_sources > 0:
            # Handle confidence calculation based on verification status AND question context
            status = analysis["verification_status"].lower()
            
            # Get the question text to analyze context
            question_context = question_text if 'question_text' in locals() else ""
            
            # For "False" claims, NO responses contribute to confidence
            if "false" in status:
                analysis["confidence_score"] = no_count / total_sources
            # For "Unsubstantiated" claims, the interpretation depends on the question context
            elif "unsubstantiated" in status or "unable to verify" in status:
                # Check if the question is asking about "evidence exists" or "origins"
                evidence_patterns = [
                    r'what evidence',
                    r'is there evidence', 
                    r'is there any evidence',
                    r'evidence.*exists',
                    r'evidence.*support',
                    r'origins of',
                    r'source of',
                    r'where.*come from'
                ]
                
                # If question asks about evidence existence, and sources say NO (no evidence),
                # then this SUPPORTS the "Unsubstantiated" verdict with high confidence
                is_evidence_question = any(re.search(pattern, question_context.lower()) for pattern in evidence_patterns)
                
                if is_evidence_question:
                    # For evidence questions, NO answers actually support the "Unsubstantiated" verdict
                    analysis["confidence_score"] = no_count / total_sources
                    print(f"--- [PARSE] Evidence-seeking question detected. NO answers support 'Unsubstantiated' verdict.")
                else:
                    # Default behavior for other types of unsubstantiated claims
                    analysis["confidence_score"] = 0.5  # Neutral confidence for unclear cases
            else:
                # For "Verified" and other positive claims, YES responses contribute to confidence
                analysis["confidence_score"] = yes_count / total_sources
        else:
            # If no sources were evaluated, use a default based on verification status
            status = analysis["verification_status"].lower()
            if "verified" in status:
                analysis["confidence_score"] = 0.85
            elif "false" in status:
                analysis["confidence_score"] = 0.85  # High confidence for false claims too
            elif "partially true" in status:
                analysis["confidence_score"] = 0.5
            elif "misleading" in status:
                analysis["confidence_score"] = 0.3
            elif "unsubstantiated" in status:
                analysis["confidence_score"] = 0.2
            else:  # Unable to verify
                analysis["confidence_score"] = 0.5
        
        # Now process the text line by line to extract the full sections
        lines = text.split("\n")
        for i, line in enumerate(lines):
            line_strip = line.strip()
            if not line_strip and not buffer:  # Skip empty lines between sections
                continue

            # Detect headers (case-insensitive)
            lower_line = line_strip.lower()
            new_section = None
            
            # Improved section detection with precise patterns
            if re.search(r'^(?:1\.|[Vv]erification\s*[Ss]tatus)', lower_line):
                new_section = "verification_status"
            elif re.search(r'^(?:2\.|[Ss]ource\s*[Ee]valuation)', lower_line):
                new_section = "source_evaluation"
            elif re.search(r'^(?:3\.|[Ss]upporting\s*[Ee]vidence)', lower_line):
                new_section = "supporting_evidence"
            elif re.search(r'^(?:4\.|[Cc]ontradicting\s*[Ee]vidence)', lower_line):
                new_section = "contradicting_evidence"
            elif re.search(r'^(?:5\.|[Rr]easoning)', lower_line):
                new_section = "reasoning"
            elif re.search(r'^(?:6\.|[Ee]vidence\s*[Gg]aps)', lower_line):
                new_section = "evidence_gaps"
            elif re.search(r'^(?:7\.|[Rr]ecommendation)', lower_line):
                new_section = "recommendations"

            # If new section detected, process buffer for previous section
            if new_section:
                # Process previous section if any
                if current_section:
                    section_content = "\n".join(filter(None, buffer)).strip()  # Join non-empty lines
                    if current_section in ["supporting_evidence", "contradicting_evidence", "evidence_gaps", "recommendations"]:
                        # Process list items with improved regex
                        items = []
                        item_buffer = ""
                        for item_line in section_content.split('\n'):
                            item_line = item_line.strip()
                            if not item_line:
                                continue
                                
                            # Check if this line starts a new list item
                            if re.match(r'^[-•*]|\d+[\.)]|\s-\s', item_line):
                                # If we have a buffer from previous item, add it
                                if item_buffer:
                                    items.append(item_buffer)
                                # Start new item buffer, removing the bullet/number
                                item_buffer = re.sub(r'^[-•*]|\d+[\.)]|\s-\s', '', item_line).strip()
                            else:
                                # Continue previous item (if exists) or start new one
                                if item_buffer:
                                    item_buffer += " " + item_line
                                else:
                                    item_buffer = item_line
                                    
                        # Add the last item if exists
                        if item_buffer:
                            items.append(item_buffer)
                            
                        analysis[current_section] = items
                    elif current_section != "source_evaluation":  # Skip source_evaluation as we've already processed it
                        analysis[current_section] = section_content
                
                # Reset buffer for new section, first line may contain the section header 
                # Extract content after the colon/period if present
                content_match = re.search(r'(?:^[0-9]+\.|\:)\s*(.*?)$', line_strip)
                if content_match:
                    buffer = [content_match.group(1)]
                else:
                    buffer = []
                current_section = new_section
            elif current_section:
                # Continue adding to buffer for the current section
                # Don't include section header definitions in the content
                if not re.match(r'^[-•*](?:\s+".*?"\s*-|\s+[A-Z].*?:)', line_strip):
                    buffer.append(line_strip)

        # Process the buffer for the last section
        if current_section and buffer and current_section != "source_evaluation":
            section_content = "\n".join(filter(None, buffer)).strip()
            if current_section in ["supporting_evidence", "contradicting_evidence", "evidence_gaps", "recommendations"]:
                # Process list items
                items = []
                item_buffer = ""
                for item_line in section_content.split('\n'):
                    item_line = item_line.strip()
                    if not item_line:
                        continue
                        
                    # Check if this line starts a new list item
                    if re.match(r'^[-•*]|\d+[\.)]|\s-\s', item_line):
                        # If we have a buffer from previous item, add it
                        if item_buffer:
                            items.append(item_buffer)
                        # Start new item buffer, removing the bullet/number
                        item_buffer = re.sub(r'^[-•*]|\d+[\.)]|\s-\s', '', item_line).strip()
                    else:
                        # Continue previous item (if exists) or start new one
                        if item_buffer:
                            item_buffer += " " + item_line
                        else:
                            item_buffer = item_line
                            
                # Add the last item if exists
                if item_buffer:
                    items.append(item_buffer)
                    
                analysis[current_section] = items
            else:  # For verification_status, reasoning
                analysis[current_section] = section_content

        # Make sure reasoning is not empty
        if not analysis["reasoning"]:
            # Try to extract reasoning from the text if the section wasn't properly identified
            reasoning_match = re.search(r'(?:5\.|[Rr]easoning:?)\s*(.*?)(?:(?:6\.|[Ee]vidence\s*[Gg]aps)|$)', text, re.DOTALL)
            if reasoning_match:
                analysis["reasoning"] = reasoning_match.group(1).strip()
            else:
                # Create a simple reasoning based on verification status
                status = analysis["verification_status"]
                analysis["reasoning"] = f"Based on the evidence, the claim is determined to be {status}."

        # Ensure confidence_score is a float
        try:
            analysis["confidence_score"] = float(analysis["confidence_score"])
        except (ValueError, TypeError):
            analysis["confidence_score"] = 0.5
            
        # Debug log the source evaluations
        print(f"--- [PARSE] Found {yes_count} YES and {no_count} NO evaluations from sources")
        print(f"--- [PARSE] Verification status: {analysis['verification_status']}")
        
        # Enhanced debugging for different question types
        status = analysis["verification_status"].lower()
        if "false" in status:
            print(f"--- [PARSE] For FALSE claims, NO answers increase confidence: {analysis['confidence_score']:.2f}")
        elif "unsubstantiated" in status or "unable to verify" in status:
            # Check if we detected an evidence-seeking question
            evidence_patterns = [
                r'what evidence', r'is there evidence', r'is there any evidence',
                r'evidence.*exists', r'evidence.*support', r'origins of',
                r'source of', r'where.*come from'
            ]
            is_evidence_question = any(re.search(pattern, question_text.lower()) for pattern in evidence_patterns)
            
            if is_evidence_question:
                print(f"--- [PARSE] Evidence-seeking question detected: '{question_text[:50]}...'")
                print(f"--- [PARSE] For UNSUBSTANTIATED claims with evidence questions, NO answers increase confidence: {analysis['confidence_score']:.2f}")
            else:
                print(f"--- [PARSE] For UNSUBSTANTIATED claims (non-evidence questions), confidence is neutral: {analysis['confidence_score']:.2f}")
        else:
            print(f"--- [PARSE] For non-FALSE claims, YES answers increase confidence: {analysis['confidence_score']:.2f}")
            
        print(f"--- [PARSE] Final confidence score: {analysis['confidence_score']}")

        return analysis 
"""
Agent responsible for making the final authenticity judgment based on fact checks.
"""
from typing import Dict, Any, List, Tuple
import re
from urllib.parse import urlparse
import logging

class JudgeAgent:
    """
    Analyzes fact-checking results to provide a final judgment on content authenticity.
    """
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the JudgeAgent.

        Args:
            config: Configuration dictionary (potentially for thresholds, etc., later).
        """
        self.config = config
        # Define thresholds for judgment (can be moved to config later)
        self.real_threshold = 0.7  # Average confidence score threshold for REAL
        self.fake_threshold = 0.3  # Average confidence score threshold for FAKE
        
        # Map verification statuses to categories for judgment
        self.verified_statuses = {
            "verified", "true", "correct", "accurate", "confirmed", "real"
        }
        self.false_statuses = {
            "false", "incorrect", "untrue", "misleading", "fake", "partially true", "partially false"
        }
        self.uncertain_statuses = {
            "unknown", "uncertain", "unable to verify", "insufficient evidence", 
            "unclear", "ambiguous", "unsubstantiated"
        }
        
        # Trusted domains for source evaluation (used as fallback)
        self.trusted_domains = {
            # Academic and research
            "edu", "ac.uk", "research", "sciencedirect.com", "nature.com", "science", 
            "ncbi.nlm.nih.gov", "pubmed", "journals", "doi.org", "springer",
            # Government
            "gov", "nih.gov", "cdc.gov", "who.int", "un.org", "europa.eu",
            # Medical 
            "mayoclinic", "clevelandclinic", "health", "medical", "medicine",
            # News outlets with fact-checking departments
            "reuters.com", "apnews.com", "bbc", "npr", "pbs",
            # Fact-checking specific sites
            "factcheck", "politifact", "snopes", "fullfact"
        }
        
        # Less reliable domains
        self.less_reliable_domains = {
            "blog", "forum", "social", "opinion", "personal",
            ".xyz", ".info", "conspiracy", "alternative", "rumor", 
            "political", "partisan", "biased"
        }

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _evaluate_sources(self, fact_checks: List[Dict[str, Any]]) -> Tuple[float, str]:
        """
        Evaluates the quality and relevance of sources when detailed analysis is missing.
        
        Returns:
            Tuple of (source_quality_score, reasoning)
        """
        total_sources = 0
        trusted_sources = 0
        questionable_sources = 0
        source_domains = set()
        source_list = []
        
        for check in fact_checks:
            sources = check.get('analysis', {}).get('sources', [])
            if not sources:
                continue
                
            total_sources += len(sources)
            for source in sources:
                if not isinstance(source, str):
                    continue
                    
                source_list.append(source)
                
                try:
                    # Extract domain from URL
                    parsed_url = urlparse(source)
                    domain = parsed_url.netloc.lower()
                    if not domain:  # If not a URL, try to extract domain-like parts
                        domain = source.lower()
                    
                    source_domains.add(domain)
                    
                    # Check if domain or parts of domain are in trusted or less reliable lists
                    is_trusted = any(trusted in domain for trusted in self.trusted_domains)
                    is_questionable = any(less_reliable in domain for less_reliable in self.less_reliable_domains)
                    
                    if is_trusted:
                        trusted_sources += 1
                    if is_questionable:
                        questionable_sources += 1
                except:
                    continue
        
        if total_sources == 0:
            return 0.0, "No sources provided for evaluation."
            
        # Calculate source quality score
        trusted_ratio = trusted_sources / total_sources
        questionable_ratio = questionable_sources / total_sources
        
        # Adjust score based on domain diversity (more diverse is better)
        diversity_factor = min(1.0, len(source_domains) / max(1, len(fact_checks)))
        
        # Calculate final score
        source_quality_score = (trusted_ratio - questionable_ratio) * diversity_factor
        source_quality_score = max(0.0, min(1.0, source_quality_score + 0.5))  # Normalize to 0-1 range with 0.5 baseline
        
        reasoning = f"Evaluated {total_sources} sources from {len(source_domains)} domains. "
        reasoning += f"Found {trusted_sources} trusted sources and {questionable_sources} potentially questionable ones. "
        reasoning += f"Source diversity factor: {diversity_factor:.2f}."
        
        return source_quality_score, reasoning

    def _calculate_average_confidence(self, fact_checks: List[Dict[str, Any]]) -> float:
        """
        Calculate the average confidence score from all fact checks.
        
        Args:
            fact_checks: List of fact check results
            
        Returns:
            Average confidence score between 0.0 and 1.0
        """
        if not fact_checks:
            return 0.0
            
        total_confidence = 0.0
        valid_checks = 0
        high_confidence_count = 0
        
        print(f"--- [JUDGE] Calculating average confidence from {len(fact_checks)} fact checks")
        
        for i, check in enumerate(fact_checks):
            try:
                status = check.get('analysis', {}).get('verification_status', '').lower()
                confidence = check.get('analysis', {}).get('confidence_score', 0.0)
                
                if isinstance(confidence, (int, float)) and confidence >= 0.0:
                    print(f"--- [JUDGE] Check #{i+1}: Status '{status}', Confidence: {confidence}")
                    # All fact checks with high confidence should contribute positively
                    # regardless of their verification status
                    total_confidence += confidence
                    valid_checks += 1
                    
                    # Count checks with 100% confidence
                    if confidence >= 0.99:
                        high_confidence_count += 1
            except Exception as e:
                print(f"--- [JUDGE] Warning: Error getting confidence from check: {e}")
                
        if valid_checks == 0:
            return 0.5  # Default if no valid confidence scores
        
        # Special case: if ALL checks have 100% confidence, return 1.0
        if high_confidence_count == valid_checks and high_confidence_count > 0:
            print(f"--- [JUDGE] All {valid_checks} checks have 100% confidence, returning 1.0")
            return 1.0
        
        avg_confidence = total_confidence / valid_checks    
        print(f"--- [JUDGE] Total confidence: {total_confidence}, Valid checks: {valid_checks}")
        print(f"--- [JUDGE] Calculated average confidence: {avg_confidence}")
        
        return avg_confidence

    def _normalize_status(self, status: str) -> str:
        """Normalize various status strings to canonical values: 'verified', 'false', 'uncertain'."""
        status_lower = status.lower().strip().replace("verification status:", "").strip()
        if status_lower in self.verified_statuses:
            return "verified"
        elif status_lower in self.false_statuses:
            return "false"
        elif status_lower in self.uncertain_statuses:
            return "uncertain"
        else:
            self.logger.warning(f"Unrecognized verification status '{status}' treated as uncertain.")
            return "uncertain"

    def judge(self, fact_checks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Makes a final judgment based on the provided fact checks.

        Args:
            fact_checks: A list of fact-checking analysis results, where each item
                         is expected to have 'verification_status' and 'confidence_score'.

        Returns:
            A dictionary containing the final judgment ('REAL', 'FAKE', 'MISLEADING', 'UNCERTAIN')
            and the calculated confidence score (0.0 to 1.0).
            Returns an error structure if input is invalid.
        """
        if not fact_checks:
            self.logger.warning("No fact checks provided to JudgeAgent.")
            return {
                "judgment": "UNCERTAIN",
                "confidence_score": 0.0,
                "reason": "No fact checks provided for judgment."
            }

        # Initialize counters and scores
        verified_count = 0
        false_count = 0
        uncertain_count = 0
        total_confidence = 0.0
        total_checks = len(fact_checks)
        highest_false_confidence = 0.0 # Track confidence of FAKE claims
        highest_verified_confidence = 0.0 # Track confidence of REAL claims
        reasons = []

        self.logger.info(f"Judging based on {total_checks} fact check analyses.")
        
        for i, analysis in enumerate(fact_checks):
            try:
                raw_status = analysis.get('verification_status', 'uncertain')
                confidence = float(analysis.get('confidence_score', 0.0))
                normalized_status = self._normalize_status(raw_status)
                reason_snippet = analysis.get('reasoning', '')[:100] # Get a snippet of reasoning if available

                self.logger.info(f"Check #{i+1}: Raw Status='{raw_status}', Norm Status='{normalized_status}', Confidence={confidence:.2f}")
                
                total_confidence += confidence

                if normalized_status == "verified":
                    verified_count += 1
                    highest_verified_confidence = max(highest_verified_confidence, confidence)
                    reasons.append(f"Claim {i+1} verified (Confidence: {confidence:.2f}). {reason_snippet}")
                elif normalized_status == "false":
                    false_count += 1
                    highest_false_confidence = max(highest_false_confidence, confidence)
                    reasons.append(f"Claim {i+1} deemed false/misleading (Confidence: {confidence:.2f}). {reason_snippet}")
                else: # uncertain
                    uncertain_count += 1
                    reasons.append(f"Claim {i+1} uncertain (Confidence: {confidence:.2f}). {reason_snippet}")

            except Exception as e:
                self.logger.error(f"Error processing fact check analysis #{i+1}: {e}", exc_info=True)
                uncertain_count += 1 # Treat errors as uncertain
                total_confidence += 0.0 # Assign zero confidence on error

        if total_checks == 0:
             average_confidence = 0.0
        else:
            average_confidence = total_confidence / total_checks
        
        # Ensure confidence is within the 0.0 to 1.0 range
        final_confidence = max(0.0, min(1.0, average_confidence))

        # Determine final judgment based on counts and confidence
        judgment = "UNCERTAIN"
        
        # Priority 1: If any claim is confidently false/misleading, judgment is FAKE or MISLEADING
        if false_count > 0 and highest_false_confidence >= 0.7:
             judgment = "FAKE"
             # Use the highest confidence of the FAKE claims as the overall confidence
             final_confidence = max(0.5, min(1.0, highest_false_confidence))
        elif false_count > 0: # If there are false claims but not high confidence
            judgment = "MISLEADING"
            # Confidence reflects average, but capped lower due to misleading nature
            final_confidence = max(0.5, min(0.8, final_confidence)) 
            
        # Priority 2: If most claims are verified with high confidence
        elif verified_count / total_checks >= 0.6 and average_confidence >= self.real_threshold:
             judgment = "REAL"
             # Confidence reflects average, potentially boosted by strong verification
             final_confidence = max(0.5, min(1.0, average_confidence))
             final_confidence = max(final_confidence, highest_verified_confidence) # Ensure it's at least the highest verified
             
        # Priority 3: If mostly uncertain or mixed low-confidence results
        else:
            judgment = "UNCERTAIN"
            # Confidence reflects the average, likely lower
            final_confidence = max(0.5, min(0.7, final_confidence)) 

        # Compile the final reasoning string
        summary_reason = f"Judgment based on {total_checks} claims: {verified_count} verified, {false_count} false/misleading, {uncertain_count} uncertain. Average Confidence: {average_confidence:.2f}. "
        summary_reason += " || ".join(reasons)

        self.logger.info(f"Final Judgment: {judgment}, Final Confidence: {final_confidence:.2f}")

        return {
            "judgment": judgment,
            "confidence_score": final_confidence,
            "reason": summary_reason
        } 
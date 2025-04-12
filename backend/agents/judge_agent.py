"""
Agent responsible for making the final authenticity judgment based on fact checks.
"""
from typing import Dict, Any, List, Tuple
import re
from urllib.parse import urlparse

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
        self.real_threshold = 0.7
        self.fake_threshold = 0.3
        
        # Map verification statuses to categories for judgment
        self.verified_statuses = {
            "verified", "true", "correct", "accurate", "confirmed"
        }
        self.false_statuses = {
            "false", "incorrect", "untrue", "misleading", "fake"
        }
        self.uncertain_statuses = {
            "unknown", "uncertain", "unable to verify", "insufficient evidence", 
            "unclear", "ambiguous", "unsubstantiated", "partially true"
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
        
        for check in fact_checks:
            try:
                confidence = check.get('analysis', {}).get('confidence_score', 0.0)
                if isinstance(confidence, (int, float)) and confidence >= 0.0:
                    total_confidence += confidence
                    valid_checks += 1
            except Exception as e:
                print(f"--- [JUDGE] Warning: Error getting confidence from check: {e}")
                
        if valid_checks == 0:
            return 0.5  # Default if no valid confidence scores
            
        return total_confidence / valid_checks

    def judge(self, fact_checks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Makes a final judgment based on the provided fact checks.

        Args:
            fact_checks: A list of fact-checking results, where each item
                         is expected to have an 'analysis' dictionary
                         containing a 'verification_status'.

        Returns:
            A dictionary containing the final judgment ('real', 'fake', 'uncertain')
            and the calculated confidence score (0.0 to 1.0).
            Returns an error structure if input is invalid.
        """
        if not fact_checks:
            print("--- [JUDGE] No fact checks provided")
            return {
                "judgment": "uncertain",
                "confidence_score": 0.0,
                "reason": "No fact checks provided."
            }

        # Initialize counters for different verification statuses
        verified_count = 0
        false_count = 0
        uncertain_count = 0
        total_checks = len(fact_checks)
        
        # Track checks with supporting evidence
        checks_with_evidence = 0
        
        # Store reasons for later summary
        verification_reasons = []

        print(f"--- [JUDGE] Analyzing {total_checks} fact checks")
        
        # First, print out all the verification statuses for debugging
        for i, check in enumerate(fact_checks):
            try:
                # Get the verification status and normalize to lowercase for comparison
                status = check.get('analysis', {}).get('verification_status', '').lower()
                
                # Get supporting evidence and reasoning - we'll use these to determine
                # if the fact check was properly completed
                supporting_evidence = check.get('analysis', {}).get('supporting_evidence', [])
                contradicting_evidence = check.get('analysis', {}).get('contradicting_evidence', [])
                reasoning = check.get('analysis', {}).get('reasoning', '')
                
                print(f"--- [JUDGE] Check #{i+1} status: '{status}'")
                print(f"--- [JUDGE] Check #{i+1} has {len(supporting_evidence)} supporting and {len(contradicting_evidence)} contradicting evidence points")
                
                # Count checks with actual evidence
                if supporting_evidence or contradicting_evidence or reasoning:
                    checks_with_evidence += 1
                
                # Collect a brief reason for this verification
                brief_reason = f"Check #{i+1}: {status.capitalize()}"
                if reasoning:
                    # Add a short excerpt from reasoning
                    brief_reason += f" - {reasoning[:80]}..." if len(reasoning) > 80 else f" - {reasoning}"
                verification_reasons.append(brief_reason)
                
            except Exception as e:
                print(f"--- [JUDGE] Warning: Error parsing check #{i+1}: {e}")

        # If few checks have proper evidence or reasoning, fall back to source evaluation
        if checks_with_evidence / total_checks < 0.5:
            print(f"--- [JUDGE] Only {checks_with_evidence}/{total_checks} checks have proper evidence or reasoning")
            print("--- [JUDGE] Falling back to source evaluation method")
            
            source_score, reasoning = self._evaluate_sources(fact_checks)
            
            print(f"--- [JUDGE] Source evaluation score: {source_score:.2f}")
            print(f"--- [JUDGE] Reasoning: {reasoning}")
            
            if source_score >= 0.7:
                judgment = "real"
                confidence_score = source_score
                print(f"--- [JUDGE] Final judgment based on sources: REAL (confidence: {confidence_score:.2f})")
            elif source_score <= 0.3:
                judgment = "fake"
                confidence_score = 1 - source_score
                print(f"--- [JUDGE] Final judgment based on sources: FAKE (confidence: {confidence_score:.2f})")
            else:
                judgment = "uncertain"
                confidence_score = 0.5
                print(f"--- [JUDGE] Final judgment based on sources: UNCERTAIN (confidence: {confidence_score:.2f})")
                
            return {
                "judgment": judgment,
                "confidence_score": confidence_score,
                "reason": reasoning
            }

        # Process all checks to categorize them
        for check in fact_checks:
            try:
                # Get the verification status and normalize
                status = check.get('analysis', {}).get('verification_status', '').lower()
                
                # Map to our categories based on the status
                if any(term in status for term in self.verified_statuses):
                    verified_count += 1
                elif any(term in status for term in self.false_statuses):
                    false_count += 1
                elif any(term in status for term in self.uncertain_statuses):
                    uncertain_count += 1
                else:
                    # For unrecognized statuses, use the confidence score to decide
                    # If confidence is high, it's likely a positive verification
                    confidence = check.get('analysis', {}).get('confidence_score', 0.0)
                    if confidence > 0.7:
                        verified_count += 1
                    elif confidence < 0.3:
                        false_count += 1
                    else:
                        uncertain_count += 1
                        
            except Exception as e:
                print(f"--- [JUDGE] Warning: Error categorizing check: {e}")
                uncertain_count += 1  # Count as uncertain if there's an error

        # If we couldn't categorize any checks properly
        if verified_count + false_count + uncertain_count == 0:
            return {
                "judgment": "uncertain",
                "confidence_score": 0.0,
                "reason": "No valid verification statuses found in fact checks."
            }

        # Calculate ratios for each category
        verified_ratio = verified_count / total_checks
        false_ratio = false_count / total_checks
        uncertain_ratio = uncertain_count / total_checks
        
        # Calculate the average confidence score from all fact checks
        average_confidence = self._calculate_average_confidence(fact_checks)
        print(f"--- [JUDGE] Average confidence from all fact checks: {average_confidence:.2f}")
        
        print(f"--- [JUDGE] Verified: {verified_count}/{total_checks} ({verified_ratio:.2f})")
        print(f"--- [JUDGE] False: {false_count}/{total_checks} ({false_ratio:.2f})")
        print(f"--- [JUDGE] Uncertain: {uncertain_count}/{total_checks} ({uncertain_ratio:.2f})")

        # Special case: If most checks are uncertain, the judgment should reflect that
        if uncertain_ratio > 0.7:
            print(f"--- [JUDGE] Final judgment: UNCERTAIN (average confidence: {average_confidence:.2f})")
            reason = "Most fact checks yielded uncertain results, suggesting insufficient evidence."
            if verification_reasons:
                reason += "\n\nSummary of key findings:\n- " + "\n- ".join(verification_reasons[:3])
            return {
                "judgment": "uncertain",
                "confidence_score": average_confidence,  # Use average confidence instead of uncertain_ratio
                "reason": reason
            }

        # Determine judgment based on verified vs. false ratios
        if verified_ratio >= self.real_threshold:
            # For verified claims, confidence is a combination of the strength of verification and the average confidence
            confidence_score = (verified_ratio + average_confidence) / 2
            print(f"--- [JUDGE] Final judgment: REAL (confidence: {confidence_score:.2f})")
            judgment = "real"
        elif false_ratio >= self.fake_threshold:
            # For false claims, confidence is a combination of the strength of falsification and the average confidence
            confidence_score = (false_ratio + average_confidence) / 2
            print(f"--- [JUDGE] Final judgment: FAKE (confidence: {confidence_score:.2f})")
            judgment = "fake"
        else:
            # If neither threshold is met, use the strongest signal
            if verified_ratio > false_ratio:
                print(f"--- [JUDGE] Final judgment: REAL with moderate confidence ({average_confidence:.2f})")
                judgment = "real"
                confidence_score = average_confidence
            elif false_ratio > verified_ratio:
                print(f"--- [JUDGE] Final judgment: FAKE with moderate confidence ({average_confidence:.2f})")
                judgment = "fake"
                confidence_score = average_confidence
            else:
                print(f"--- [JUDGE] Final judgment: UNCERTAIN (equal evidence for both sides)")
                judgment = "uncertain"
                confidence_score = average_confidence

        # Create a detailed reason including summary of key findings
        reason = f"Based on {verified_count} verified, {false_count} false, and {uncertain_count} uncertain fact checks."
        if verification_reasons:
            reason += "\n\nSummary of key findings:\n- " + "\n- ".join(verification_reasons[:3])
            
        return {
            "judgment": judgment,
            "confidence_score": confidence_score,
            "reason": reason
        } 
"""
Defines different personalities for the agents in the system.
"""

class AgentPersonality:
    """Represents a single agent personality with all its attributes."""
    
    def __init__(self, name: str, role: str, traits: list, communication_style: str, expertise: list):
        self.name = name
        self.role = role
        self.traits = traits
        self.communication_style = communication_style
        self.expertise = expertise

class AgentPersonalities:
    """Contains predefined personalities for different agents."""
    
    @classmethod
    def get_fact_checker(cls) -> AgentPersonality:
        return AgentPersonality(
            name="Fact Checker",
            role="fact-checker",
            traits=["analytical", "precise", "thorough"],
            communication_style="evidence-based and methodical",
            expertise=["fact verification", "source evaluation", "logical analysis"]
        )
    
    @classmethod
    def get_question_generator(cls) -> AgentPersonality:
        return AgentPersonality(
            name="Question Generator",
            role="question-generator",
            traits=["curious", "exploratory", "comprehensive"],
            communication_style="inquisitive and systematic",
            expertise=["question formulation", "topic exploration", "information gathering"]
        )
    
    @classmethod
    def get_fact_questioner(cls) -> AgentPersonality:
        return AgentPersonality(
            name="Fact Questioner",
            role="fact-questioner",
            traits=["skeptical", "methodical", "thorough"],
            communication_style="probing and analytical",
            expertise=["claim identification", "verification strategy", "critical analysis"]
        )
    
    @classmethod
    def get_questioning(cls) -> AgentPersonality:
        return AgentPersonality(
            name="Questioning Agent",
            role="questioning",
            traits=["inquisitive", "probing", "investigative"],
            communication_style="targeted and systematic",
            expertise=["deep questioning", "information gathering", "analysis"]
        ) 
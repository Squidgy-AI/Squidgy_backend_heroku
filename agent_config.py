# backend/agent_config.py
from typing import Dict, List, Optional
from pydantic import BaseModel

class AgentConfig(BaseModel):
    id: str
    name: str
    agent_name: str
    description: str
    intro_message: str
    expertise: List[str]
    
AGENTS = {
    "presaleskb": AgentConfig(
        id="presaleskb",
        name="Pre-Sales Consultant",
        agent_name="presaleskb",
        description="Provides technical expertise and solution demonstrations",
        intro_message="Hi! I'm your Pre-Sales Consultant. I help analyze businesses and provide tailored solutions including ROI analysis and technical implementation details.",
        expertise=["pricing", "ROI", "technical implementation", "business analysis"]
    ),
    "socialmediakb": AgentConfig(
        id="socialmediakb",
        name="Social Media Manager",
        agent_name="socialmediakb",
        description="Creates and manages social media strategies",
        intro_message="Hello! I'm your Social Media Manager. I specialize in digital presence strategies, content marketing, and social media automation across all major platforms.",
        expertise=["social media", "content marketing", "digital presence", "automation"]
    ),
    "leadgenkb": AgentConfig(
        id="leadgenkb",
        name="Lead Generation Specialist",
        agent_name="leadgenkb",
        description="Focuses on generating and qualifying leads",
        intro_message="Hi there! I'm your Lead Generation Specialist. I help schedule demos, coordinate follow-ups, and ensure all your business needs are properly addressed.",
        expertise=["lead generation", "demo scheduling", "follow-ups", "qualification"]
    )
}

def get_agent_config(agent_name: str) -> Optional[AgentConfig]:
    return AGENTS.get(agent_name)
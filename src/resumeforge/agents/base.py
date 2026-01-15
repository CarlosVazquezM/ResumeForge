"""Base agent interface."""

from abc import ABC, abstractmethod
from typing import Any

from resumeforge.schemas.blackboard import Blackboard


class BaseAgent(ABC):
    """Base class for all agents in the pipeline."""
    
    def __init__(self, provider: "BaseProvider", config: dict):
        """
        Initialize agent.
        
        Args:
            provider: LLM provider instance
            config: Agent configuration dictionary
        """
        self.provider = provider
        self.config = config
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 4096)
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    @abstractmethod
    def build_user_prompt(self, blackboard: Blackboard) -> str:
        """Build the user prompt from blackboard state."""
        pass
    
    @abstractmethod
    def parse_response(self, response: str, blackboard: Blackboard) -> Blackboard:
        """Parse LLM response and update blackboard."""
        pass
    
    def execute(self, blackboard: Blackboard) -> Blackboard:
        """
        Execute this agent's task.
        
        Args:
            blackboard: Current blackboard state
            
        Returns:
            Updated blackboard state
        """
        # TODO: Implement agent execution
        # See SDD Section 4.1 for implementation details
        raise NotImplementedError(f"{self.__class__.__name__} not yet implemented")


# Forward reference for type hints
from resumeforge.providers.base import BaseProvider  # noqa: E402

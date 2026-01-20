"""Base agent interface."""

import json
import time
from abc import ABC, abstractmethod

import structlog

from resumeforge.exceptions import ProviderError, ValidationError
from resumeforge.schemas.blackboard import Blackboard
from resumeforge.utils.cost_estimator import estimate_cost

logger = structlog.get_logger(__name__)

# Constants
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 4096
MAX_RESPONSE_PREVIEW_LENGTH = 500
MARKDOWN_JSON_PREFIX_LENGTH = 7  # Length of "```json"
MARKDOWN_PREFIX_LENGTH = 3  # Length of "```"
MARKDOWN_SUFFIX_LENGTH = 3  # Length of "```"


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
        self.temperature = config.get("temperature", DEFAULT_TEMPERATURE)
        self.max_tokens = config.get("max_tokens", DEFAULT_MAX_TOKENS)
        self.logger = logger.bind(
            agent=self.__class__.__name__,
            model=provider.model,
            temperature=self.temperature
        )
    
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
            
        Raises:
            ProviderError: If LLM call fails
            ValidationError: If response parsing fails
        """
        start_time = time.time()
        self.logger.info("Executing agent", step=blackboard.current_step)
        
        # Get prompts
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(blackboard)
        
        # Count input tokens
        input_tokens = self.provider.count_tokens(system_prompt + user_prompt)
        self.logger.debug("Token estimates", input_tokens=input_tokens, max_output_tokens=self.max_tokens)
        
        # Call LLM
        try:
            # Try to use JSON mode for OpenAI if available
            kwargs = {}
            if hasattr(self.provider, "model") and "gpt" in self.provider.model.lower():
                kwargs["response_format"] = {"type": "json_object"}
            
            response = self.provider.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                **kwargs
            )
            
            # Count output tokens
            output_tokens = self.provider.count_tokens(response)
            
            self.logger.debug("Received LLM response", response_length=len(response))
            
        except ProviderError:
            # Re-raise ProviderError without wrapping (preserves original error message)
            raise
        except Exception as e:
            self.logger.error("LLM call failed", error=str(e))
            raise ProviderError(f"Failed to execute {self.__class__.__name__}: {e}") from e
        
        # Calculate execution time and cost
        execution_time = time.time() - start_time
        
        # Get provider name for cost estimation
        provider_name = self.provider.__class__.__name__.replace("Provider", "").lower()
        # Handle OpenAI -> openai, Anthropic -> anthropic, etc.
        if provider_name == "openai":
            provider_name = "openai"
        elif provider_name == "anthropic":
            provider_name = "anthropic"
        elif provider_name == "google":
            provider_name = "google"
        elif provider_name == "groq":
            provider_name = "groq"
        
        # Estimate cost
        cost_info = estimate_cost(
            provider_name=provider_name,
            model=self.provider.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        cost_usd = cost_info.get("estimated_cost_usd", 0.0)
        
        # Log performance metrics
        self.logger.info(
            "Agent execution completed",
            execution_time_seconds=execution_time,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost_usd,
            provider=provider_name,
            model=self.provider.model,
        )
        
        # Store metrics in blackboard if available (set by orchestrator)
        # Use getattr with default to avoid AttributeError
        performance_metrics = getattr(blackboard, "performance_metrics", None)
        if performance_metrics:
            # Convert CamelCase class name to snake_case agent name
            # e.g., "JDAnalystAgent" -> "jd_analyst", "EvidenceMapperAgent" -> "evidence_mapper"
            class_name = self.__class__.__name__.replace("Agent", "")
            agent_name = self._camel_to_snake(class_name)
            performance_metrics.record_agent_execution(
                agent_name=agent_name,
                duration=execution_time,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost_usd,
            )
        
        # Parse and update blackboard
        try:
            updated_blackboard = self.parse_response(response, blackboard)
            return updated_blackboard
            
        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to parse JSON response",
                error=str(e),
                response_preview=response[:MAX_RESPONSE_PREVIEW_LENGTH]
            )
            raise ValidationError(f"Invalid JSON response from {self.__class__.__name__}: {e}") from e
        except ValidationError:
            # Re-raise ValidationError without wrapping (e.g., from parse_response validation)
            raise
        except Exception as e:
            self.logger.error("Failed to parse response", error=str(e))
            raise ValidationError(f"Failed to parse response from {self.__class__.__name__}: {e}") from e
    
    @staticmethod
    def _camel_to_snake(name: str) -> str:
        """
        Convert CamelCase to snake_case.
        
        Examples:
            "JDAnalyst" -> "jd_analyst"
            "EvidenceMapper" -> "evidence_mapper"
            "ResumeWriter" -> "resume_writer"
            "Auditor" -> "auditor"
        
        Args:
            name: CamelCase string
            
        Returns:
            snake_case string
        """
        import re
        # Insert underscore before uppercase letters (except at start)
        # Then convert to lowercase
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        return s2.lower()
    
    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks.
        
        Args:
            text: Raw LLM response
            
        Returns:
            JSON string
        """
        text = text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[MARKDOWN_JSON_PREFIX_LENGTH:]  # Remove ```json
        elif text.startswith("```"):
            text = text[MARKDOWN_PREFIX_LENGTH:]  # Remove ```
        
        if text.endswith("```"):
            text = text[:-MARKDOWN_SUFFIX_LENGTH]  # Remove closing ```
        
        return text.strip()


# Forward reference for type hints
from resumeforge.providers.base import BaseProvider  # noqa: E402

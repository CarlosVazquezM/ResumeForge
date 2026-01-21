"""Base agent interface."""

import json
import re
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
    
    def restore_from_cache(self, blackboard: Blackboard, cached_result: dict) -> Blackboard | None:
        """
        Restore blackboard from cached result.
        
        Override this method in agents to restore state from cache.
        Return None to fall through to normal execution.
        
        Args:
            blackboard: Current blackboard state
            cached_result: Cached result dict
            
        Returns:
            Updated blackboard, or None to skip cache
        """
        return None  # Default: don't use cache
    
    def extract_cache_result(self, blackboard: Blackboard) -> dict | None:
        """
        Extract result from blackboard for caching.
        
        Override this method in agents to specify what to cache.
        Return None to skip caching.
        
        Args:
            blackboard: Updated blackboard after execution
            
        Returns:
            Dict to cache, or None to skip
        """
        return None  # Default: don't cache
    
    def get_cache_key_inputs(self, blackboard: Blackboard) -> tuple | None:
        """
        Get inputs for cache key computation.
        
        Override this method in agents to enable caching.
        Return a tuple of values that uniquely identify the agent's inputs.
        Return None to disable caching for this agent.
        
        Args:
            blackboard: Current blackboard state
            
        Returns:
            Tuple of cache inputs, or None to disable caching
        """
        return None  # Default: no caching
    
    def get_cache_result(self, blackboard: Blackboard) -> dict | None:
        """
        Get cached result if available.
        
        Args:
            blackboard: Current blackboard state
            
        Returns:
            Cached result dict if found, None otherwise
        """
        cache_inputs = self.get_cache_key_inputs(blackboard)
        if cache_inputs is None:
            return None
        
        # Get cache instance from blackboard if available
        cache = getattr(blackboard, "_llm_cache", None)
        if cache is None:
            return None
        
        # Get agent name (e.g., "jd_analyst")
        class_name = self.__class__.__name__.replace("Agent", "")
        agent_name = self._camel_to_snake(class_name)
        
        return cache.get(agent_name, *cache_inputs)
    
    def save_cache_result(self, blackboard: Blackboard, result: dict) -> None:
        """
        Save result to cache.
        
        Args:
            blackboard: Current blackboard state
            result: Result dict to cache
        """
        cache_inputs = self.get_cache_key_inputs(blackboard)
        if cache_inputs is None:
            return
        
        # Get cache instance from blackboard if available
        cache = getattr(blackboard, "_llm_cache", None)
        if cache is None:
            return
        
        # Get agent name
        class_name = self.__class__.__name__.replace("Agent", "")
        agent_name = self._camel_to_snake(class_name)
        
        cache.set(agent_name, result, *cache_inputs)
    
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
        
        # Check cache first
        cached_result = self.get_cache_result(blackboard)
        if cached_result is not None:
            self.logger.info("Cache hit - restoring from cache")
            # Restore blackboard from cache (agents override this if needed)
            restored = self.restore_from_cache(blackboard, cached_result)
            if restored is not None:
                execution_time = time.time() - start_time
                self.logger.info(
                    "Agent execution completed (from cache)",
                    execution_time_seconds=execution_time,
                    cached=True
                )
                return restored
            # If restore_from_cache returns None, fall through to normal execution
        
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
            
            # Save to cache if caching is enabled
            cache_inputs = self.get_cache_key_inputs(blackboard)
            if cache_inputs is not None:
                # Extract result for caching (agents can override extract_cache_result)
                cache_result = self.extract_cache_result(updated_blackboard)
                if cache_result is not None:
                    self.save_cache_result(blackboard, cache_result)
            
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
    
    def _repair_json(self, json_text: str) -> str:
        """
        Attempt to repair common JSON issues like unterminated strings.
        
        This is a best-effort repair for common issues. It handles:
        - Unterminated strings (response cut off mid-string)
        - Missing closing braces/brackets
        - Trailing commas before closing structures
        
        Args:
            json_text: Potentially malformed JSON string
            
        Returns:
            Repaired JSON string (may still be invalid)
        """
        repaired = json_text.strip()
        
        # Count open/close braces and brackets BEFORE any repairs
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')
        
        # Check if we're in the middle of a string (odd number of unescaped quotes)
        # Simple heuristic: count quotes, but this doesn't handle escaped quotes perfectly
        quote_count = repaired.count('"')
        
        # Also check for strings ending with single quotes (common truncation pattern)
        # If the last non-whitespace character before a comma/brace/bracket is a single quote,
        # we likely have an unterminated string
        ends_with_single_quote = repaired.rstrip().endswith("'")
        
        # If we have an odd number of quotes, we might be in an unterminated string
        if quote_count % 2 == 1 or ends_with_single_quote:
            # Find the last quote
            last_quote_pos = repaired.rfind('"')
            if last_quote_pos >= 0:
                # Check what comes after the last quote
                after_quote = repaired[last_quote_pos + 1:].strip()
                # If it doesn't look like valid JSON continuation, try to close the string
                if not after_quote or (after_quote and after_quote[0] not in (',', ':', '}', ']', '\n')):
                    # We're likely in an unterminated string
                    # If it ends with a single quote, replace it with a double quote
                    if ends_with_single_quote:
                        repaired = repaired.rstrip()[:-1] + '"'
                    else:
                        # Close the string by appending a quote (don't truncate, just add closing quote)
                        repaired = repaired + '"'
            elif ends_with_single_quote:
                # No double quote found but ends with single quote - replace it
                repaired = repaired.rstrip()[:-1] + '"'
        
        # Handle truncated key-value pairs BEFORE removing trailing commas and closing structures
        # This handles cases where JSON is cut off like "key": with no value
        # Check for keys that typically have array values (common in ATS reports)
        array_keys = ['supported_keywords', 'missing_keywords', 'format_warnings', 'items', 'list']
        for key in array_keys:
            # Replace "key": at end of string (most important - handles truncation)
            repaired = re.sub(rf'"{re.escape(key)}":\s*$', rf'"{key}": []', repaired)
            # Also handle "key": followed by whitespace and closing brace (single brace)
            # Pattern uses } to match single closing brace; }} in replacement f-string becomes single } in output
            # Use regular raw string for pattern to avoid f-string brace escaping issues
            pattern = r'"' + re.escape(key) + r'":\s*}'
            repaired = re.sub(pattern, rf'"{key}": []}}', repaired)
            pattern_newline = r'"' + re.escape(key) + r'":\s*\n\s*}'
            repaired = re.sub(pattern_newline, rf'"{key}": []\n}}', repaired)
        
        # Handle any remaining truncated key-value pairs (key: with no value)
        # Replace "key": at end of string with "key": null
        repaired = re.sub(r'"([^"]+)":\s*$', r'"\1": null', repaired)
        # Also handle "key": } patterns (single brace)
        # Pattern uses } to match single closing brace; replacement uses single } (not }} since this is a raw string)
        repaired = re.sub(r'"([^"]+)":\s*}', r'"\1": null}', repaired)
        repaired = re.sub(r'"([^"]+)":\s*\n\s*}', r'"\1": null\n}', repaired)
        
        # Remove trailing commas before closing structures (JSON doesn't allow trailing commas)
        # First, remove trailing commas that are already before existing closing brackets/braces
        repaired = re.sub(r',\s*\]', ']', repaired)
        repaired = re.sub(r',\s*}', '}', repaired)
        
        # Now close any open structures in reverse order (brackets first, then braces)
        # But BEFORE adding closing brackets, remove any trailing commas at the end
        # This handles cases like: "item",] where we're about to add ]
        if open_brackets > 0:
            # Remove trailing comma before we add closing bracket
            repaired = re.sub(r',\s*$', '', repaired)
            repaired += ']' * open_brackets
        if open_braces > 0:
            # Remove trailing comma before we add closing brace
            repaired = re.sub(r',\s*$', '', repaired)
            repaired += '}' * open_braces
        
        # Final pass: remove any trailing commas that might have been created
        repaired = re.sub(r',\s*\]', ']', repaired)
        repaired = re.sub(r',\s*}', '}', repaired)
        
        return repaired
    
    def _parse_json_with_repair(self, json_text: str, context: str = "response") -> dict:
        """
        Parse JSON with automatic repair attempt on failure.
        
        Args:
            json_text: JSON string to parse
            context: Context string for error messages (e.g., "ATS Scorer")
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            ValidationError: If JSON cannot be parsed even after repair attempt
        """
        # First, try to parse as-is
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            # Log the problematic JSON for debugging
            preview_length = min(len(json_text), MAX_RESPONSE_PREVIEW_LENGTH)
            self.logger.warning(
                f"JSON parse failed for {context}, attempting repair",
                error=str(e),
                error_position=f"line {e.lineno}, column {e.colno}",
                json_preview=json_text[:preview_length],
                json_length=len(json_text)
            )
            
            # Try to repair
            repaired_json = self._repair_json(json_text)
            
            # Try parsing again
            try:
                return json.loads(repaired_json)
            except json.JSONDecodeError as e2:
                # Repair failed, log response for debugging
                # Log full response if it's small, otherwise log preview
                max_log_length = 2000
                log_original = json_text if len(json_text) <= max_log_length else json_text[:max_log_length] + "..."
                log_repaired = repaired_json if len(repaired_json) <= max_log_length else repaired_json[:max_log_length] + "..."
                
                self.logger.error(
                    f"JSON repair failed for {context}",
                    original_error=str(e),
                    repair_error=str(e2),
                    original_json=log_original,
                    repaired_json=log_repaired,
                    original_length=len(json_text),
                    repaired_length=len(repaired_json)
                )
                raise ValidationError(
                    f"Invalid JSON response from {context}: {e}. "
                    f"Response length: {len(json_text)} chars. "
                    f"Preview (first {preview_length} chars): {json_text[:preview_length]}"
                ) from e2


# Forward reference for type hints
from resumeforge.providers.base import BaseProvider  # noqa: E402

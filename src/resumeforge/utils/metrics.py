"""Performance metrics collection and timing utilities."""

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from resumeforge.utils.cost_estimator import PRICING

logger = structlog.get_logger(__name__)


@contextmanager
def timed_operation(operation_name: str):
    """
    Context manager for timing operations.
    
    Args:
        operation_name: Name of the operation being timed
        
    Example:
        with timed_operation("JD Analysis"):
            result = agent.execute(blackboard)
    """
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        logger.info(
            "Operation timing",
            operation=operation_name,
            duration_seconds=elapsed,
            duration_ms=elapsed * 1000,
        )


class PerformanceMetrics:
    """Collect performance metrics for pipeline execution."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.agent_times: dict[str, list[float]] = {}
        self.token_counts: dict[str, dict[str, int]] = {}
        self.costs: dict[str, float] = {}
        self.start_time: float | None = None
        self.end_time: float | None = None
    
    def record_agent_execution(
        self,
        agent_name: str,
        duration: float,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost: float | None = None,
    ) -> None:
        """
        Record agent execution metrics.
        
        Args:
            agent_name: Name of the agent (e.g., "jd_analyst")
            duration: Execution duration in seconds
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated
            cost: Cost in USD for this execution
        """
        if agent_name not in self.agent_times:
            self.agent_times[agent_name] = []
            self.token_counts[agent_name] = {}
            self.costs[agent_name] = 0.0
        
        self.agent_times[agent_name].append(duration)
        
        if input_tokens is not None:
            self.token_counts[agent_name]["input_tokens"] = (
                self.token_counts[agent_name].get("input_tokens", 0) + input_tokens
            )
        if output_tokens is not None:
            self.token_counts[agent_name]["output_tokens"] = (
                self.token_counts[agent_name].get("output_tokens", 0) + output_tokens
            )
        
        if cost is not None:
            self.costs[agent_name] += cost
    
    def start_pipeline(self) -> None:
        """Mark the start of pipeline execution."""
        self.start_time = time.time()
    
    def end_pipeline(self) -> None:
        """Mark the end of pipeline execution."""
        self.end_time = time.time()
    
    def get_total_duration(self) -> float | None:
        """
        Get total pipeline duration.
        
        Returns:
            Duration in seconds, or None if pipeline not completed
        """
        if self.start_time is None or self.end_time is None:
            return None
        return self.end_time - self.start_time
    
    def get_total_cost(self) -> float:
        """
        Get total cost across all agents.
        
        Returns:
            Total cost in USD
        """
        return sum(self.costs.values())
    
    def get_total_tokens(self, token_type: str = "total") -> int:
        """
        Get total tokens across all agents.
        
        Args:
            token_type: "input", "output", or "total"
            
        Returns:
            Total token count
        """
        total = 0
        for agent_tokens in self.token_counts.values():
            if token_type == "input":
                total += agent_tokens.get("input_tokens", 0)
            elif token_type == "output":
                total += agent_tokens.get("output_tokens", 0)
            else:  # total
                total += agent_tokens.get("input_tokens", 0) + agent_tokens.get(
                    "output_tokens", 0
                )
        return total
    
    def get_summary(self) -> dict:
        """
        Get a summary of all collected metrics.
        
        Returns:
            Dictionary with summary statistics
        """
        summary = {
            "total_duration_seconds": self.get_total_duration(),
            "total_cost_usd": self.get_total_cost(),
            "total_tokens": self.get_total_tokens(),
            "total_input_tokens": self.get_total_tokens("input"),
            "total_output_tokens": self.get_total_tokens("output"),
            "agents": {},
        }
        
        for agent_name in self.agent_times:
            times = self.agent_times[agent_name]
            summary["agents"][agent_name] = {
                "execution_count": len(times),
                "total_time_seconds": sum(times),
                "avg_time_seconds": sum(times) / len(times) if times else 0,
                "min_time_seconds": min(times) if times else 0,
                "max_time_seconds": max(times) if times else 0,
                "tokens": self.token_counts.get(agent_name, {}).copy(),
                "cost_usd": self.costs.get(agent_name, 0.0),
            }
        
        return summary
    
    def log_summary(self) -> None:
        """Log a summary of all collected metrics."""
        summary = self.get_summary()
        logger.info(
            "Performance metrics summary",
            **summary,
        )

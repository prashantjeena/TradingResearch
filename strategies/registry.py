"""Small, explicit registry for independently runnable research strategies."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass


StrategyRunner = Callable[["StrategyDefinition"], int]
"""Callable contract for one independently executable strategy workflow."""


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    """Metadata and executable runner for one registered strategy."""

    name: str
    output_slug: str
    display_name: str
    runner: StrategyRunner


class StrategyRegistry:
    """Resolve explicitly requested strategies without fallback behavior."""

    def __init__(self, strategies: Iterable[StrategyDefinition]) -> None:
        """Store registered strategies in deterministic registration order.

        Args:
            strategies: Strategies available for explicit execution.

        Raises:
            ValueError: If a strategy name or output slug is registered twice.
        """
        registered = tuple(strategies)
        names = [strategy.name for strategy in registered]
        slugs = [strategy.output_slug for strategy in registered]
        if len(names) != len(set(names)) or len(slugs) != len(set(slugs)):
            raise ValueError("Strategy names and output slugs must be unique.")
        self._strategies = registered
        self._by_name = {strategy.name: strategy for strategy in registered}

    @property
    def names(self) -> tuple[str, ...]:
        """Return registered strategy names in execution order."""
        return tuple(strategy.name for strategy in self._strategies)

    def select(self, requested_strategy: str) -> tuple[StrategyDefinition, ...]:
        """Resolve one registered strategy or every registered strategy once.

        Args:
            requested_strategy: A registered strategy name or ``"all"``.

        Returns:
            One selected strategy, or all registered strategies in order.

        Raises:
            ValueError: If the requested name is not registered and is not
                ``"all"``.
        """
        if requested_strategy == "all":
            return self._strategies
        try:
            return (self._by_name[requested_strategy],)
        except KeyError as error:
            valid_names = ", ".join((*self.names, "all"))
            raise ValueError(f"Unsupported strategy {requested_strategy!r}. Valid values: {valid_names}.") from error

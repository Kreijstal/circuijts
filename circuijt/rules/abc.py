# -*- coding: utf-8 -*-
"""Abstract base class for circuit transformation rules."""

from abc import ABC, abstractmethod
from typing import List, Any


class RuleInterface(ABC):
    """
    Abstract base class defining the interface for circuit transformation rules.

    All concrete rule implementations must inherit from this class and implement
    the required abstract methods.
    """

    @abstractmethod
    def get_name(self) -> str:
        """
        Get the name of this rule.

        Returns:
            str: A human-readable name for the rule.
        """
        pass

    @abstractmethod
    def find_candidates(self, circuit) -> List[Any]:
        """
        Find all candidates in the circuit where this rule can be applied.

        Args:
            circuit: A Circuit object to search for candidates.

        Returns:
            List[Any]: A list of candidates where the rule can be applied.
                      The format of each candidate is rule-specific.
        """
        pass

    @abstractmethod
    def apply_to_candidate(self, circuit, candidate) -> None:
        """
        Apply the rule transformation to a specific candidate in the circuit.

        This method modifies the circuit's graph and DSU in-place.

        Args:
            circuit: A Circuit object to modify.
            candidate: A candidate returned by find_candidates() to transform.
        """
        pass

    def get_description(self) -> str:
        """
        Get a description of what this rule does.

        Returns:
            str: A human-readable description of the rule's behavior.
        """
        return f"Rule: {self.get_name()}"

    def can_apply(self, circuit) -> bool:
        """
        Check if this rule can be applied to the circuit.

        Args:
            circuit: A Circuit object to check.

        Returns:
            bool: True if the rule can be applied (has candidates), False otherwise.
        """
        return len(self.find_candidates(circuit)) > 0

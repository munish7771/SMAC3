from abc import ABC, abstractmethod
from typing import List, Any


# Base class for ranking methods
class RankingMethod(ABC):
    @abstractmethod
    def rank(self, configurations: List[Any], objectives: List[Any]) -> List[int]:
        pass

class SingleObjectiveRanking(RankingMethod):
    def rank(self, configurations: List[Any], objectives: List[Any]) -> List[int]:
        return sorted(range(len(configurations)), key=lambda i: objectives[i])

class ParetoRanking(RankingMethod):
    def rank(self, configurations: List[Any], objectives: List[Any]) -> List[int]:
        # Implementation of Pareto front ranking for multi-objective optimization
        def dominates(p1, p2):
            return all(x <= y for x, y in zip(p1, p2)) and any(x < y for x, y in zip(p1, p2))

        ranked = []
        for i, obj in enumerate(objectives):
            non_dominated = True
            for j in range(len(objectives)):
                if i != j and dominates(objectives[j], obj):
                    non_dominated = False
                    break
            if non_dominated:
                ranked.append(i)
        return ranked

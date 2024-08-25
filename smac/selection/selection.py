from ranking import RankingMethod
from typing import List, Any

class IncumbentSelection:
    def __init__(self, ranking_method: RankingMethod):
        self.ranking_method = ranking_method

    def select(self, configurations: List[Any], objectives: List[Any]) -> Any:
        ranked_indices = self.ranking_method.rank(configurations, objectives)
        best_index = ranked_indices[0]
        return configurations[best_index]
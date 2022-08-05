from __future__ import annotations

from smac.acquisition_function.expected_improvement import EI
from smac.acquisition_optimizer.local_and_random_search import (
    LocalAndSortedRandomSearch,
)
from smac.chooser.random_chooser import ChooserProb
from smac.configspace import Configuration
from smac.facade import Facade
from smac.initial_design.sobol_design import SobolInitialDesign
from smac.intensification.intensification import Intensifier
from smac.model.random_forest.rf_with_instances import RandomForestWithInstances
from smac.model.utils import get_types
from smac.multi_objective import AbstractMultiObjectiveAlgorithm
from smac.multi_objective.aggregation_strategy import MeanAggregationStrategy
from smac.runhistory.runhistory_transformer import RunhistoryLogScaledTransformer
from smac.scenario import Scenario

__copyright__ = "Copyright 2018, ML4AAD"
__license__ = "3-clause BSD"


class HyperparameterFacade(Facade):
    @staticmethod
    def get_model(
        scenario: Scenario,
        *,
        n_trees: int = 10,
        bootstrapping: bool = True,
        ratio_features: float = 1.0,
        min_samples_split: int = 2,
        min_samples_leaf: int = 1,
        max_depth: int = 2**20,
    ) -> RandomForestWithInstances:
        types, bounds = get_types(scenario.configspace)

        return RandomForestWithInstances(
            types=types,
            bounds=bounds,
            log_y=True,
            num_trees=n_trees,
            do_bootstrapping=bootstrapping,
            ratio_features=ratio_features,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            max_depth=max_depth,
            configspace=scenario.configspace,
            seed=scenario.seed,
        )

    @staticmethod
    def get_acquisition_function(scenario: Scenario, *, par: float = 0.0) -> EI:
        return EI(par=par, log=True)

    @staticmethod
    def get_acquisition_optimizer(
        scenario: Scenario,
        *,
        local_search_iterations: int = 10,
        challengers: int = 10000,
    ) -> LocalAndSortedRandomSearch:
        optimizer = LocalAndSortedRandomSearch(
            scenario.configspace,
            local_search_iterations=local_search_iterations,
            challengers=challengers,
            seed=scenario.seed,
        )

        return optimizer

    @staticmethod
    def get_intensifier(scenario: Scenario, *, min_challenger=1, min_config_calls=1, max_config_calls=3) -> Intensifier:
        intensifier = Intensifier(
            instances=scenario.instances,
            instance_specifics=scenario.instance_specifics,
            algorithm_walltime_limit=scenario.algorithm_walltime_limit,
            deterministic=scenario.deterministic,
            min_challenger=min_challenger,
            race_against=scenario.configspace.get_default_configuration(),
            min_config_calls=min_config_calls,
            max_config_calls=max_config_calls,
            seed=scenario.seed,
        )

        return intensifier

    @staticmethod
    def get_initial_design(
        scenario: Scenario,
        *,
        initial_configs: list[Configuration] | None = None,
        n_configs_per_hyperparamter: int = 10,
        max_config_ratio: float = 0.25,  # Use at most X*budget in the initial design
    ) -> SobolInitialDesign:
        return SobolInitialDesign(
            configspace=scenario.configspace,
            n_runs=scenario.n_runs,
            configs=initial_configs,
            n_configs_per_hyperparameter=n_configs_per_hyperparamter,
            max_config_ratio=max_config_ratio,
            seed=scenario.seed,
        )

    @staticmethod
    def get_random_configuration_chooser(scenario: Scenario, *, probability: float = 0.2) -> ChooserProb:
        return ChooserProb(prob=probability)

    @staticmethod
    def get_multi_objective_algorithm(scenario: Scenario) -> AbstractMultiObjectiveAlgorithm | None:
        if len(scenario.objectives) <= 1:
            return None

        return MeanAggregationStrategy(scenario.seed)

    @staticmethod
    def get_runhistory_transformer(scenario: Scenario) -> RunhistoryLogScaledTransformer:
        return RunhistoryLogScaledTransformer(
            scenario,
            n_params=len(scenario.configspace.get_hyperparameters()),
            seed=scenario.seed,
        )
from __future__ import annotations

from smac.acquisition_function import AbstractAcquisitionFunction
from smac.acquisition_function.expected_improvement import EI
from smac.acquisition_optimizer import AbstractAcquisitionOptimizer
from smac.acquisition_optimizer.local_and_random_search import (
    LocalAndSortedRandomSearch,
)
from smac.chooser.random_chooser import ChooserProb, RandomChooser
from smac.configspace import Configuration
from smac.facade import Facade
from smac.initial_design import InitialDesign
from smac.initial_design.default_configuration_design import DefaultInitialDesign
from smac.intensification.intensification import Intensifier
from smac.model.random_forest.rf_with_instances import RandomForestWithInstances
from smac.model.utils import get_types
from smac.multi_objective import AbstractMultiObjectiveAlgorithm
from smac.multi_objective.aggregation_strategy import MeanAggregationStrategy
from smac.runhistory.runhistory_transformer import RunhistoryTransformer
from smac.scenario import Scenario
from smac.utils.logging import get_logger

__copyright__ = "Copyright 2018, ML4AAD"
__license__ = "3-clause BSD"


logger = get_logger(__name__)


class AlgorithmConfigurationFacade(Facade):
    @staticmethod
    def get_model(
        scenario: Scenario,
        *,
        n_trees: int = 10,
        bootstrapping: bool = True,
        ratio_features: float = 5.0 / 6.0,
        min_samples_split: int = 3,
        min_samples_leaf: int = 3,
        max_depth: int = 20,
        pca_components: int = 4,
    ) -> RandomForestWithInstances:
        types, bounds = get_types(scenario.configspace, scenario.instance_features)

        return RandomForestWithInstances(
            types=types,
            bounds=bounds,
            log_y=False,
            num_trees=n_trees,
            do_bootstrapping=bootstrapping,
            ratio_features=ratio_features,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            max_depth=max_depth,
            configspace=scenario.configspace,
            instance_features=scenario.instance_features,
            pca_components=pca_components,
            seed=scenario.seed,
        )

    @staticmethod
    def get_acquisition_function(scenario: Scenario, par: float = 0.0) -> EI:
        return EI(par=par)

    @staticmethod
    def get_acquisition_optimizer(scenario: Scenario) -> AbstractAcquisitionOptimizer:
        optimizer = LocalAndSortedRandomSearch(
            scenario.configspace,
            seed=scenario.seed,
        )

        return optimizer

    @staticmethod
    def get_intensifier(
        scenario: Scenario,
        *,
        min_challenger=1,
        min_config_calls=1,
        max_config_calls=2000,
    ) -> Intensifier:
        if scenario.deterministic:
            min_challenger = 1

        intensifier = Intensifier(
            instances=scenario.instances,
            instance_specifics=scenario.instance_specifics,  # What is that?
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
    def get_initial_design(scenario: Scenario, *, initial_configs: list[Configuration] | None = None) -> InitialDesign:
        return DefaultInitialDesign(
            configspace=scenario.configspace,
            n_runs=scenario.n_runs,
            configs=initial_configs,
            n_configs_per_hyperparameter=0,
            seed=scenario.seed,
        )

    @staticmethod
    def get_random_configuration_chooser(scenario: Scenario, *, random_probability: float = 0.5) -> RandomChooser:
        return ChooserProb(prob=random_probability, seed=scenario.seed)

    @staticmethod
    def get_multi_objective_algorithm(scenario: Scenario) -> AbstractMultiObjectiveAlgorithm | None:
        if len(scenario.objectives) <= 1:
            return None

        return MeanAggregationStrategy(scenario.seed)

    @staticmethod
    def get_runhistory_transformer(scenario: Scenario) -> RunhistoryTransformer:
        transformer = RunhistoryTransformer(
            scenario=scenario,
            n_params=len(scenario.configspace.get_hyperparameters()),
            scale_percentage=5,
            seed=scenario.seed,
        )

        return transformer
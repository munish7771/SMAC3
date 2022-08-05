import unittest
import unittest.mock

import numpy as np
from ConfigSpace import ConfigurationSpace, UniformFloatHyperparameter

from smac.initial_design.sobol_design import SobolInitialDesign

__copyright__ = "Copyright 2021, AutoML.org Freiburg-Hannover"
__license__ = "3-clause BSD"


class TestSobol(unittest.TestCase):
    def test_sobol(self):
        cs = ConfigurationSpace()
        hyperparameters = [UniformFloatHyperparameter("x%d" % (i + 1), 0, 1) for i in range(21201)]
        cs.add_hyperparameters(hyperparameters)

        sobol_kwargs = dict(
            n_runs=1000,
            configs=None,
            n_configs_per_hyperparameter=None,
            max_config_ratio=0.25,
            init_budget=1,
            seed=1,
        )
        SobolInitialDesign(configspace=cs, **sobol_kwargs).select_configurations()

        cs.add_hyperparameter(UniformFloatHyperparameter("x21202", 0, 1))
        with self.assertRaisesRegex(
            Exception,
            "Maximum supported dimensionality is 21201.",
        ):
            SobolInitialDesign(configspace=cs, **sobol_kwargs).select_configurations()
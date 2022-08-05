from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

import inspect
import math
import time
import traceback

import numpy as np
from pynisher import MemoryLimitException, WallTimeoutException, limit

from smac.configspace import Configuration
from smac.constants import MAXINT
from smac.runner import StatusType
from smac.runner.serial_runner import SerialRunner
from smac.utils.logging import get_logger
from smac.utils.stats import Stats

__copyright__ = "Copyright 2015, ML4AAD"
__license__ = "3-clause BSD"

logger = get_logger(__name__)


class AbstractTargetAlgorithmRunner(SerialRunner):
    """Baseclass to execute target algorithms which are python functions.

    Note
    ----
    Do not use this class directly.
    """

    def __init__(
        self,
        target_algorithm: Callable,
        stats: Stats,
        objectives: list[str] = ["cost"],
        par_factor: int = 1,
        crash_cost: float | list[float] = float(MAXINT),
        abort_on_first_run_crash: bool = True,
        memory_limit: int | None = None,
        algorithm_walltime_limit: float | None = None,
    ):
        super().__init__(
            target_algorithm=target_algorithm,
            stats=stats,
            objectives=objectives,
            par_factor=par_factor,
            crash_cost=crash_cost,
            abort_on_first_run_crash=abort_on_first_run_crash,
        )
        self.target_algorithm = target_algorithm
        self.stats = stats
        self.objectives = objectives

        self.par_factor = par_factor
        self.crash_cost = crash_cost
        self.abort_on_first_run_crash = abort_on_first_run_crash

        signature = inspect.signature(target_algorithm).parameters
        self._accepts_seed = "seed" in signature.keys()
        self._accepts_instance = "instance" in signature.keys()
        self._accepts_budget = "budget" in signature.keys()

        if not callable(target_algorithm):
            raise TypeError(f"Argument `target_algorithm` must be a callable but is type `{type(target_algorithm)}`.")
        self._target_algorithm = cast(Callable, target_algorithm)

        # Pynisher limitations
        if memory_limit is not None:
            memory_limit = int(math.ceil(memory_limit))

        if algorithm_walltime_limit is not None:
            algorithm_walltime_limit = int(math.ceil(algorithm_walltime_limit))

        self.memory_limit = memory_limit
        self.algorithm_walltime_limit = algorithm_walltime_limit

    def run(
        self,
        config: Configuration,
        instance: str | None = None,
        seed: int = 0,
        budget: float | None = None,
        instance_specific: str = "0",
    ) -> Tuple[StatusType, float | list[float], float, Dict]:
        """Calls the target algorithm with pynisher (if algorithm walltime limit or memory limit is set) or without."""

        # The kwargs are passed to the target algorithm.
        kwargs: Dict[str, Any] = {}
        if self._accepts_seed:
            kwargs["seed"] = seed
        if self._accepts_instance:
            kwargs["instance"] = instance
        if self._accepts_budget:
            kwargs["budget"] = budget

        # Presetting
        cost = self.crash_cost
        runtime = 0.0
        additional_info = {}
        status = StatusType.CRASHED

        # If memory limit or walltime limit is set, we wanna use pynisher
        if self.memory_limit is not None or self.algorithm_walltime_limit is not None:
            target_algorithm = limit(
                self._target_algorithm,
                memory=self.memory_limit,
                wall_time=self.algorithm_walltime_limit,
                wrap_errors=True,  # Hard to describe; see https://github.com/automl/pynisher
            )
        else:
            target_algorithm = self._target_algorithm

        # Call target algorithm
        try:
            start_time = time.time()
            rval = self._call_target_algorithm(target_algorithm, config, kwargs)
            runtime = time.time() - start_time
            status = StatusType.SUCCESS
        except WallTimeoutException:
            status = StatusType.TIMEOUT
        except MemoryLimitException:
            status = StatusType.MEMOUT
        except Exception as e:
            cost = np.asarray(cost).squeeze().tolist()
            additional_info = {
                "traceback": traceback.format_exc(),
                "error": repr(e),
            }
            status = StatusType.CRASHED

        if status != StatusType.SUCCESS:
            return status, cost, runtime, additional_info

        if isinstance(rval, tuple):
            result = rval[0]
            additional_info = rval[1]
        else:
            result = rval
            additional_info = {}

        # We update cost based on our result
        cost = result

        # Do some sanity checking (for multi objective)
        if len(self.objectives) > 1:
            error = f"Returned costs {cost} does not match the number of objectives {len(self.objectives)}."

            # If dict convert to array make sure the ordering is correct.
            if isinstance(cost, dict):
                ordered_cost = []
                for name in self.objectives:
                    if name not in cost:
                        raise RuntimeError(f"Objective {name} was not found in the returned costs.")

                    ordered_cost.append(cost[name])
                cost = ordered_cost

            if isinstance(cost, list):
                if len(cost) != len(self.objectives):
                    raise RuntimeError(error)

            if isinstance(cost, float):
                raise RuntimeError(error)

        if cost is None:
            status = StatusType.CRASHED
            cost = self.crash_cost

        # We want to get either a float or a list of floats.
        cost = np.asarray(cost).squeeze().tolist()

        return status, cost, runtime, additional_info

    def _call_target_algorithm(
        self,
        obj: Callable,
        config: Configuration,
        obj_kwargs: Dict[str, Union[int, str, float, None]],
    ) -> Union[float, Tuple[float, Dict]]:
        raise NotImplementedError()


class TargetAlgorithmRunner(AbstractTargetAlgorithmRunner):
    """Evaluate function for given configuration and resource limit.

    Passes the configuration as a dictionary to the target algorithm. The
    target algorithm needs to implement one of the following signatures:

    * ``target_algorithm(config: Configuration) -> Union[float, Tuple[float, Any]]``
    * ``target_algorithm(config: Configuration, seed: int) -> Union[float, Tuple[float, Any]]``
    * ``target_algorithm(config: Configuration, seed: int, instance: str) -> Union[float, Tuple[float, Any]]``

    The target algorithm can either return a float (the loss), or a tuple
    with the first element being a float and the second being additional run
    information.

    ExecuteTAFuncDict will use inspection to figure out the correct call to
    the target algorithm.

    Parameters
    ----------
    ta : callable
        Function (target algorithm) to be optimized.
    stats : smac.stats.stats.Stats, optional
        Stats object to collect statistics about runtime etc.
    run_obj : str, optional
        Run objective (runtime or quality)
    memory_limit : int, optional
        Memory limit (in MB) that will be applied to the target algorithm.
    par_factor : int, optional
        Penalized average runtime factor. Only used when `run_obj='runtime'`
    use_pynisher: bool, optional
        use pynisher to limit resources;
    """

    def _call_target_algorithm(
        self,
        obj: Callable,
        config: Configuration,
        obj_kwargs: Dict[str, Union[int, str, float, None]],
    ) -> Union[float, Tuple[float, Dict]]:

        return obj(config, **obj_kwargs)


'''
# TODO: For what do we need this one?
class ExecuteTAFuncArray(AbstractAlgorithmExecuter):
    """Evaluate function for given configuration and resource limit.

    Passes the configuration as an array-like to the target algorithm. The
    target algorithm needs to implement one of the following signatures:

    * ``target_algorithm(config: np.ndarray) -> Union[float, Tuple[float, Any]]``
    * ``target_algorithm(config: np.ndarray, seed: int) -> Union[float, Tuple[float, Any]]``
    * ``target_algorithm(config: np.ndarray, seed: int, instance: str) -> Union[float, Tuple[float, Any]]``

    The target algorithm can either return a float (the loss), or a tuple
    with the first element being a float and the second being additional run
    information.

    ExecuteTAFuncDict will use inspection to figure out the correct call to
    the target algorithm.

    Parameters
    ----------
    ta : callable
        Function (target algorithm) to be optimized.
    stats : smac.stats.stats.Stats, optional
        Stats object to collect statistics about runtime etc.
    run_obj: str, optional
        Run objective (runtime or quality)
    memory_limit : int, optional
        Memory limit (in MB) that will be applied to the target algorithm.
    par_factor: int, optional
        Penalized average runtime factor. Only used when `run_obj='runtime'`
    """

    def _call_target_algorithm(
        self,
        obj: Callable,
        config: Configuration,
        obj_kwargs: Dict[str, Union[int, str, float, None]],
    ) -> Union[float, Tuple[float, Dict]]:

        x = np.array([val for _, val in sorted(config.get_dictionary().items())], dtype=float)
        return obj(x, **obj_kwargs)
'''
from __future__ import annotations

from typing import Optional

import warnings

import numpy as np
from scipy.stats import truncnorm

import smac.model.base_imputor
from smac.model.base_model import BaseModel
from smac.utils.logging import get_logger

__copyright__ = "Copyright 2015, ML4AAD"
__license__ = "3-clause BSD"


logger = get_logger(__name__)


class RFRImputator(smac.model.base_imputor.BaseImputor):
    """Imputor using pyrfr's Random Forest regressor.

    Note
    ----
    Sets var_threshold as the lower bound on the variance for the
    predictions of the random forest.

    Parameters
    ----------
    rng : np.random.RandomState
        Will be used to draw a seed (currently not used)
    algorithm_walltime_limit : float
        algorithm_walltime_limit value for this scenario (upper runnning time limit)
    threshold : float
        Highest possible values (e.g. algorithm_walltime_limit * parX).
    model : BaseEPM
        Predictive model (i.e. RandomForestWithInstances)
    change_threshold : float
        Stop imputation if change is less than this.
    max_iter : int
        Maximum number of imputation iterations.

    Attributes
    ----------
    max_iter : int
    change_threshold : float
    algorithm_walltime_limit : float
    threshold : float
    seed : int
        Created by drawing random int from rng
    model : BaseEPM
        Predictive model (i.e. RandomForestWithInstances)
    var_threshold: float
    """

    def __init__(
        self,
        algorithm_walltime_limit: float,
        threshold: float,
        model: BaseModel,
        change_threshold: float = 0.01,
        max_iter: int = 2,
        seed: int = 0,
    ):
        super(RFRImputator, self).__init__()
        self.max_iter = max_iter
        self.change_threshold = change_threshold
        self.algorithm_walltime_limit = algorithm_walltime_limit
        self.threshold = threshold
        self.seed = np.random.RandomState(seed)
        self.model = model

        # Never use a lower variance than this
        self.var_threshold = 10**-2

    def impute(
        self,
        censored_X: np.ndarray,
        censored_y: np.ndarray,
        uncensored_X: np.ndarray,
        uncensored_y: np.ndarray,
    ) -> Optional[np.ndarray]:
        """Imputes censored runs and returns new y values.

        Parameters
        ----------
        censored_X : np.ndarray [N, M]
            Feature array of all censored runs.
        censored_y : np.ndarray [N, 1]
            Target values for all runs censored runs.
        uncensored_X : np.ndarray [N, M]
            Feature array of all non-censored runs.
        uncensored_y : np.ndarray [N, 1]
            Target values for all non-censored runs.

        Returns
        -------
        imputed_y : np.ndarray
            Same shape as censored_y [N, 1]
        """
        if censored_X.shape[0] == 0:
            logger.critical("Nothing to impute. None is returned.")
            return None

        censored_y = censored_y.flatten()
        uncensored_y = uncensored_y.flatten()

        # first learn model without censored data
        self.model.train(uncensored_X, uncensored_y)

        logger.debug("Going to impute %d y-values with %s" % (censored_X.shape[0], str(self.model)))

        imputed_y = None  # define this, if imputation fails

        # Define variables
        y = np.empty((0,))  # This only defines the type, the actual value will not be used later on.

        it = 1
        change = 0

        while True:
            logger.debug("Iteration %d of %d" % (it, self.max_iter))

            # predict censored y values
            y_mean, y_var = self.model.predict(censored_X)
            assert y_var is not None  # please mypy

            y_var[y_var < self.var_threshold] = self.var_threshold
            y_stdev = np.sqrt(y_var)[:, 0]
            y_mean = y_mean[:, 0]

            # ignore the warnings of truncnorm.stats
            # since we handle them appropriately
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", r"invalid value encountered in (subtract|true_divide|power).*")
                warnings.filterwarnings("ignore", r"divide by zero encountered in (true_divide|log).*")
                imputed_y = truncnorm.stats(
                    a=(censored_y - y_mean) / y_stdev,
                    b=(self.threshold - y_mean) / y_stdev,
                    loc=y_mean,
                    scale=y_stdev,
                    moments="m",
                )

            imputed_y = np.array(imputed_y)

            nans = ~np.isfinite(imputed_y)
            n_nans = sum(nans)
            if n_nans > 0:
                # Replace all nans with maximum of predicted perf and censored value
                # this happens if the prediction is far smaller than the
                # censored data point
                logger.debug("Going to replace %d nan-value(s) with " "max(captime, predicted mean)" % n_nans)
                imputed_y[nans] = np.max([censored_y[nans], y_mean[nans]], axis=0)

            if it > 1:
                # Calc mean difference between imputed values this and last
                # iteration, assume imputed values are always concatenated
                # after uncensored values

                change = np.mean(np.abs(imputed_y - y[uncensored_y.shape[0] :]) / y[uncensored_y.shape[0] :])

            # lower all values that are higher than threshold
            # should probably never happen
            imputed_y[imputed_y >= self.threshold] = self.threshold

            logger.debug("Change: %f" % change)

            X = np.concatenate((uncensored_X, censored_X))
            y = np.concatenate((uncensored_y, imputed_y))

            if change > self.change_threshold or it == 1:
                self.model.train(X, y)
            else:
                break

            it += 1
            if it > self.max_iter:
                break

        logger.debug("Imputation used %d/%d iterations, last_change=%f" % (it - 1, self.max_iter, change))

        # replace all y > algorithm_walltime_limit with PAR10 values (i.e., threshold)
        imputed_y = np.array(imputed_y, dtype=float)
        imputed_y[imputed_y >= self.algorithm_walltime_limit] = self.threshold

        if not np.isfinite(imputed_y).all():
            logger.critical("Imputed values are not finite, %s" % str(imputed_y))
        return np.reshape(imputed_y, [imputed_y.shape[0], 1])
from unittest.mock import MagicMock

import pandas as pd
import pytest

from evalml import AutoMLSearch
from evalml.automl.automl_algorithm import DefaultAlgorithm, IterativeAlgorithm
from evalml.exceptions import ObjectiveNotFoundError
from evalml.model_family import ModelFamily
from evalml.objectives import MeanSquaredLogError, RootMeanSquaredLogError
from evalml.pipelines import (
    PipelineBase,
    RegressionPipeline,
    TimeSeriesRegressionPipeline,
)
from evalml.pipelines.components.utils import get_estimators
from evalml.pipelines.utils import make_pipeline
from evalml.preprocessing import TimeSeriesSplit
from evalml.problem_types import ProblemTypes


def test_callback_iterative(X_y_regression):
    X, y = X_y_regression

    counts = {
        "start_iteration_callback": 0,
        "add_result_callback": 0,
    }

    def start_iteration_callback(pipeline, automl_obj, counts=counts):
        counts["start_iteration_callback"] += 1

    def add_result_callback(results, trained_pipeline, automl_obj, counts=counts):
        counts["add_result_callback"] += 1

    max_iterations = 3
    automl = AutoMLSearch(
        X_train=X,
        y_train=y,
        problem_type="regression",
        objective="R2",
        max_iterations=max_iterations,
        start_iteration_callback=start_iteration_callback,
        add_result_callback=add_result_callback,
        n_jobs=1,
        _automl_algorithm="iterative",
    )
    automl.search()

    assert counts["start_iteration_callback"] == len(get_estimators("regression")) + 1
    assert counts["add_result_callback"] == max_iterations


def test_automl_component_graphs_no_allowed_component_graphs_iterative(X_y_regression):
    X, y = X_y_regression
    with pytest.raises(ValueError, match="No allowed pipelines to search"):
        AutoMLSearch(
            X_train=X,
            y_train=y,
            problem_type="regression",
            allowed_component_graphs=None,
            allowed_model_families=[],
            _automl_algorithm="iterative",
        )


def test_automl_allowed_component_graphs_specified_component_graphs_iterative(
    AutoMLTestEnv,
    dummy_regressor_estimator_class,
    dummy_regression_pipeline,
    X_y_regression,
):
    X, y = X_y_regression

    automl = AutoMLSearch(
        X_train=X,
        y_train=y,
        problem_type="regression",
        allowed_component_graphs={
            "Mock Regression Pipeline": [dummy_regressor_estimator_class]
        },
        allowed_model_families=None,
        _automl_algorithm="iterative",
    )
    env = AutoMLTestEnv("regression")
    expected_component_graph = dummy_regression_pipeline.component_graph
    expected_name = dummy_regression_pipeline.name
    expected_oarameters = dummy_regression_pipeline.parameters
    assert automl.allowed_pipelines[0].component_graph == expected_component_graph
    assert automl.allowed_pipelines[0].name == expected_name
    assert automl.allowed_pipelines[0].parameters == expected_oarameters
    assert automl.allowed_model_families == [ModelFamily.NONE]

    with env.test_context(score_return_value={automl.objective.name: 1.0}):
        automl.search()
    env.mock_fit.assert_called()
    env.mock_score.assert_called()
    assert automl.allowed_pipelines[0].component_graph == expected_component_graph
    assert automl.allowed_pipelines[0].name == expected_name
    assert automl.allowed_pipelines[0].parameters == expected_oarameters
    assert automl.allowed_model_families == [ModelFamily.NONE]


def test_automl_allowed_component_graphs_specified_allowed_model_families_iterative(
    AutoMLTestEnv, X_y_regression, assert_allowed_pipelines_equal_helper
):
    X, y = X_y_regression
    automl = AutoMLSearch(
        X_train=X,
        y_train=y,
        problem_type="regression",
        allowed_component_graphs=None,
        allowed_model_families=[ModelFamily.RANDOM_FOREST],
        _automl_algorithm="iterative",
    )
    expected_pipelines = [
        make_pipeline(X, y, estimator, ProblemTypes.REGRESSION)
        for estimator in get_estimators(
            ProblemTypes.REGRESSION, model_families=[ModelFamily.RANDOM_FOREST]
        )
    ]
    assert_allowed_pipelines_equal_helper(automl.allowed_pipelines, expected_pipelines)
    assert set(automl.allowed_model_families) == set([ModelFamily.RANDOM_FOREST])
    env = AutoMLTestEnv("regression")
    with env.test_context(score_return_value={automl.objective.name: 1.0}):
        automl.search()

    automl = AutoMLSearch(
        X_train=X,
        y_train=y,
        problem_type="regression",
        allowed_component_graphs=None,
        allowed_model_families=["random_forest"],
        _automl_algorithm="iterative",
    )
    expected_pipelines = [
        make_pipeline(X, y, estimator, ProblemTypes.REGRESSION)
        for estimator in get_estimators(
            ProblemTypes.REGRESSION, model_families=[ModelFamily.RANDOM_FOREST]
        )
    ]
    assert_allowed_pipelines_equal_helper(automl.allowed_pipelines, expected_pipelines)
    assert set(automl.allowed_model_families) == set([ModelFamily.RANDOM_FOREST])
    with env.test_context(score_return_value={automl.objective.name: 1.0}):
        automl.search()
    env.mock_fit.assert_called()
    env.mock_score.assert_called()


def test_automl_allowed_component_graphs_init_allowed_both_not_specified_iterative(
    AutoMLTestEnv, X_y_regression, assert_allowed_pipelines_equal_helper
):
    X, y = X_y_regression
    automl = AutoMLSearch(
        X_train=X,
        y_train=y,
        problem_type="regression",
        allowed_component_graphs=None,
        allowed_model_families=None,
        _automl_algorithm="iterative",
    )
    expected_pipelines = [
        make_pipeline(X, y, estimator, ProblemTypes.REGRESSION)
        for estimator in get_estimators(ProblemTypes.REGRESSION, model_families=None)
    ]
    assert_allowed_pipelines_equal_helper(automl.allowed_pipelines, expected_pipelines)
    assert set(automl.allowed_model_families) == set(
        [p.model_family for p in expected_pipelines]
    )
    env = AutoMLTestEnv("regression")
    with env.test_context(score_return_value={automl.objective.name: 1.0}):
        automl.search()
    env.mock_fit.assert_called()
    env.mock_score.assert_called()


def test_automl_allowed_component_graphs_init_allowed_both_specified_iterative(
    AutoMLTestEnv,
    dummy_regressor_estimator_class,
    dummy_regression_pipeline,
    X_y_regression,
    assert_allowed_pipelines_equal_helper,
):
    X, y = X_y_regression
    automl = AutoMLSearch(
        X_train=X,
        y_train=y,
        problem_type="regression",
        allowed_component_graphs={
            "Mock Regression Pipeline": [dummy_regressor_estimator_class]
        },
        allowed_model_families=[ModelFamily.RANDOM_FOREST],
        _automl_algorithm="iterative",
    )
    expected_pipelines = [dummy_regression_pipeline]
    assert_allowed_pipelines_equal_helper(automl.allowed_pipelines, expected_pipelines)
    assert set(automl.allowed_model_families) == set(
        [p.model_family for p in expected_pipelines]
    )
    env = AutoMLTestEnv("regression")
    with env.test_context(score_return_value={automl.objective.name: 1.0}):
        automl.search()
    env.mock_fit.assert_called()
    env.mock_score.assert_called()


def test_automl_allowed_component_graphs_search_iterative(
    AutoMLTestEnv,
    example_regression_graph,
    X_y_regression,
):
    X, y = X_y_regression
    component_graph = {"CG": example_regression_graph}

    start_iteration_callback = MagicMock()
    automl = AutoMLSearch(
        X_train=X,
        y_train=y,
        problem_type="regression",
        max_iterations=2,
        start_iteration_callback=start_iteration_callback,
        allowed_component_graphs=component_graph,
        _automl_algorithm="iterative",
    )
    env = AutoMLTestEnv("regression")
    with env.test_context(score_return_value={automl.objective.name: 1.0}):
        automl.search()

    assert start_iteration_callback.call_count == 2
    assert isinstance(
        start_iteration_callback.call_args_list[0][0][0], RegressionPipeline
    )
    assert isinstance(
        start_iteration_callback.call_args_list[1][0][0], RegressionPipeline
    )

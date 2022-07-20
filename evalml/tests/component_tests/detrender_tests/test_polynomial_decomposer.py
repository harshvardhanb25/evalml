import numpy as np
import pandas as pd
import pytest
import woodwork as ww
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

from evalml.pipelines.components import PolynomialDecomposer


def test_polynomial_decomposer_init():
    delayed_features = PolynomialDecomposer(degree=3)
    assert delayed_features.parameters == {"degree": 3}


def test_polynomial_decomposer_init_raises_error_if_degree_not_int():

    with pytest.raises(TypeError, match="Received str"):
        PolynomialDecomposer(degree="1")

    with pytest.raises(TypeError, match="Received float"):
        PolynomialDecomposer(degree=3.4)

    _ = PolynomialDecomposer(degree=3.0)


def test_polynomial_decomposer_raises_value_error_target_is_none(ts_data):
    X, y = ts_data

    with pytest.raises(ValueError, match="y cannot be None for PolynomialDecomposer!"):
        PolynomialDecomposer(degree=3).fit_transform(X, None)

    with pytest.raises(ValueError, match="y cannot be None for PolynomialDecomposer!"):
        PolynomialDecomposer(degree=3).fit(X, None)

    pdt = PolynomialDecomposer(degree=3).fit(X, y)

    with pytest.raises(ValueError, match="y cannot be None for PolynomialDecomposer!"):
        pdt.inverse_transform(None)


def test_polynomial_decomposer_raises_value_error_transform_fit_data_freq_mismatch(
    ts_data,
):
    X, y = ts_data

    pdc = PolynomialDecomposer(degree=3).fit(X, y)

    with pytest.raises(ValueError, match="Cannot transform given data with frequency"):
        # Change target data frequency to monthly to mismatch daily frequency of fixture
        y = y.asfreq("m")
        pdc.transform(X, y)


def test_polynomial_decomposer_get_trend_df_raises_errors(ts_data):
    X, y = ts_data
    pdt = PolynomialDecomposer(degree=3)
    pdt.fit_transform(X, y)

    with pytest.raises(
        TypeError, match="Provided X should have datetimes in the index."
    ):
        X_int_index = X.reset_index()
        pdt.get_trend_dataframe(X_int_index, y)

    with pytest.raises(TypeError, match="y must be pd.Series or pd.DataFrame!"):
        y = np.array(y.values)
        pdt.get_trend_dataframe(X, y)

    with pytest.raises(
        ValueError,
        match="Provided DatetimeIndex of X should have an inferred frequency.",
    ):
        X.index.freq = None
        pdt.get_trend_dataframe(X, y)


@pytest.mark.parametrize("input_type", ["pd", "ww"])
@pytest.mark.parametrize("degree", [1, 2, 3])
def test_polynomial_decomposer_fit_transform(degree, input_type, ts_data):

    X_input, y_input = ts_data

    # Get the expected answer
    lin_reg = LinearRegression(fit_intercept=True)
    features = PolynomialFeatures(degree=degree).fit_transform(
        np.arange(X_input.shape[0]).reshape(-1, 1),
    )
    lin_reg.fit(features, y_input)
    detrended_values = y_input.values - lin_reg.predict(features)
    expected_index = y_input.index if input_type != "np" else range(y_input.shape[0])
    expected_answer = pd.Series(detrended_values, index=expected_index)

    X, y = X_input, y_input

    if input_type == "ww":
        X = X_input.copy()
        X.ww.init()
        y = ww.init_series(y_input.copy())

    output_X, output_y = PolynomialDecomposer(degree=degree).fit_transform(X, y)
    pd.testing.assert_series_equal(expected_answer, output_y)

    # Verify the X is not changed
    pd.testing.assert_frame_equal(X, output_X)


@pytest.mark.parametrize(
    "variateness",
    [
        "univariate",
        "multivariate",
    ],
)
@pytest.mark.parametrize("input_type", ["pd", "ww"])
@pytest.mark.parametrize("degree", [1, 2, 3])
def test_polynomial_decomposer_get_trend_dataframe(
    degree,
    input_type,
    variateness,
    ts_data,
    ts_data_quadratic_trend,
    ts_data_cubic_trend,
):

    if degree == 1:
        X_input, y_input = ts_data
    elif degree == 2:
        X_input, y_input = ts_data_quadratic_trend
    elif degree == 3:
        X_input, y_input = ts_data_cubic_trend

    # Get the expected answer
    lin_reg = LinearRegression(fit_intercept=True)
    features = PolynomialFeatures(degree=degree).fit_transform(
        np.arange(X_input.shape[0]).reshape(-1, 1)
    )
    lin_reg.fit(features, y_input)
    detrended_values = y_input.values - lin_reg.predict(features)
    expected_index = y_input.index if input_type != "np" else range(y_input.shape[0])
    expected_answer = pd.Series(detrended_values, index=expected_index)

    X, y = X_input, y_input

    if input_type == "ww":
        X = X_input.copy()
        X.ww.init()
        y = ww.init_series(y_input.copy())

    pdt = PolynomialDecomposer(degree=degree)
    output_X, output_y = pdt.fit_transform(X, y)
    pd.testing.assert_series_equal(expected_answer, output_y)

    # get_trend_dataframe() is only expected to work with datetime indices
    if variateness == "univariate":
        y = y
    elif variateness == "multivariate":
        y = pd.concat([y, y], axis=1)
    result_dfs = pdt.get_trend_dataframe(X, y)

    def get_trend_df_format_correct(df):
        return set(df.columns) == {"trend", "seasonality", "residual"}

    def get_trend_df_values_correct(df, y):
        np.testing.assert_array_almost_equal(
            (df["trend"] + df["seasonality"] + df["residual"]).values, y.values
        )

    assert isinstance(result_dfs, list)
    assert all(isinstance(x, pd.DataFrame) for x in result_dfs)
    assert all(get_trend_df_format_correct(x) for x in result_dfs)
    if variateness == "univariate":
        assert len(result_dfs) == 1
        [get_trend_df_values_correct(x, y) for x in result_dfs]
    elif variateness == "multivariate":
        assert len(result_dfs) == 2
        [get_trend_df_values_correct(x, y[idx]) for idx, x in enumerate(result_dfs)]


@pytest.mark.parametrize("degree", [1, 2, 3])
def test_polynomial_decomposer_inverse_transform(degree, ts_data):
    X, y = ts_data

    decomposer = PolynomialDecomposer(degree=degree)
    output_X, output_y = decomposer.fit_transform(X, y)
    output_inverse_y = decomposer.inverse_transform(output_y)
    pd.testing.assert_series_equal(y, output_inverse_y, check_dtype=False)


def test_polynomial_decomposer_needs_monotonic_index(ts_data):
    X, y = ts_data
    decomposer = PolynomialDecomposer(degree=2)

    with pytest.raises(Exception) as exec_info:
        y_shuffled = y.sample(frac=1, replace=False)
        decomposer.fit_transform(X, y_shuffled)
    expected_errors = ["monotonically", "X must be in an sktime compatible format"]
    assert any([error in str(exec_info.value) for error in expected_errors])
    with pytest.raises(
        Exception,
    ):
        y_string_index = pd.Series(np.arange(31), index=[f"row_{i}" for i in range(31)])
        decomposer.fit_transform(X, y_string_index)

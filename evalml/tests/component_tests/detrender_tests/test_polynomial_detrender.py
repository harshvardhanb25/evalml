import numpy as np
import pandas as pd
import pytest
import woodwork as ww
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

from evalml.pipelines.components import PolynomialDetrender


def test_polynomial_detrender_init():
    delayed_features = PolynomialDetrender(degree=3)
    assert delayed_features.parameters == {"degree": 3}


def test_polynomial_detrender_init_raises_error_if_degree_not_int():

    with pytest.raises(TypeError, match="Received str"):
        PolynomialDetrender(degree="1")

    with pytest.raises(TypeError, match="Received float"):
        PolynomialDetrender(degree=3.4)

    _ = PolynomialDetrender(degree=3.0)


def test_polynomial_detrender_raises_value_error_target_is_none(ts_data):
    X, y = ts_data

    with pytest.raises(ValueError, match="y cannot be None for PolynomialDetrender!"):
        PolynomialDetrender(degree=3).fit_transform(X, None)

    with pytest.raises(ValueError, match="y cannot be None for PolynomialDetrender!"):
        PolynomialDetrender(degree=3).fit(X, None)

    pdt = PolynomialDetrender(degree=3).fit(X, y)

    with pytest.raises(ValueError, match="y cannot be None for PolynomialDetrender!"):
        pdt.inverse_transform(None)


def test_polynomial_detrender_get_trend_df_raises_errors(ts_data):
    X, y = ts_data
    pdt = PolynomialDetrender(degree=3)
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


@pytest.mark.parametrize("input_type", ["np", "pd", "ww"])
@pytest.mark.parametrize("use_int_index", [True, False])
@pytest.mark.parametrize("degree", [1, 2, 3])
def test_polynomial_detrender_fit_transform(degree, use_int_index, input_type, ts_data):

    X_input, y_input = ts_data
    if use_int_index:
        X_input.index = np.arange(X_input.shape[0])
        y_input.index = np.arange(y_input.shape[0])

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

    if input_type == "np":
        X = X_input.values
        y = y_input.values
    elif input_type == "ww":
        X = X_input.copy()
        X.ww.init()
        y = ww.init_series(y_input.copy())

    output_X, output_y = PolynomialDetrender(degree=degree).fit_transform(X, y)
    pd.testing.assert_series_equal(expected_answer, output_y)

    # Verify the X is not changed
    if input_type == "np":
        np.testing.assert_equal(X, output_X)
    else:
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
def test_polynomial_detrender_get_trend_dataframe(
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

    pdt = PolynomialDetrender(degree=degree)
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
def test_polynomial_detrender_inverse_transform(degree, ts_data):
    X, y = ts_data

    detrender = PolynomialDetrender(degree=degree)
    output_X, output_y = detrender.fit_transform(X, y)
    output_inverse_y = detrender.inverse_transform(output_y)
    pd.testing.assert_series_equal(y, output_inverse_y, check_dtype=False)


def test_polynomial_detrender_needs_monotonic_index(ts_data):
    X, y = ts_data
    detrender = PolynomialDetrender(degree=2)

    with pytest.raises(Exception) as exec_info:
        y_shuffled = y.sample(frac=1, replace=False)
        detrender.fit_transform(X, y_shuffled)
    expected_errors = ["monotonically", "X must be in an sktime compatible format"]
    assert any([error in str(exec_info.value) for error in expected_errors])
    with pytest.raises(
        Exception,
    ):
        y_string_index = pd.Series(np.arange(31), index=[f"row_{i}" for i in range(31)])
        detrender.fit_transform(X, y_string_index)

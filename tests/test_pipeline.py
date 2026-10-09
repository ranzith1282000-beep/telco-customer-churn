"""Data quality checks for the churn pipeline. Run with: pytest"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pipeline  # noqa: E402


@pytest.fixture(scope="module")
def raw():
    return pipeline.load_raw()


@pytest.fixture(scope="module")
def v1(raw):
    return pipeline.build_v1(raw)


@pytest.fixture(scope="module")
def v2(v1):
    return pipeline.build_v2(v1)


def test_no_rows_lost(raw, v1, v2):
    assert len(raw) == len(v1) == len(v2) == 7043


def test_customer_ids_unique(v1):
    assert v1["customerID"].is_unique


def test_total_charges_numeric_and_filled(v1):
    assert v1["total_charges"].notna().all()
    # The 11 blank TotalCharges rows are brand-new customers (tenure 0).
    blanks = v1["TotalCharges"].str.strip() == ""
    assert blanks.sum() == 11
    assert (v1.loc[blanks, "tenure"] == 0).all()
    assert (v1.loc[blanks, "total_charges"] == 0).all()


def test_contract_month_mapping(v1):
    assert set(v1["contract_month"]) == {1, 12, 24}


def test_service_columns_collapsed(v1):
    for col in ["multiple_lines", *pipeline.SERVICE_COLUMNS.values()]:
        assert set(v1[col]) == {"Yes", "No"}


def test_v2_fully_numeric(v2):
    assert all(dtype.kind in "if" for dtype in v2.dtypes)
    assert set(v2["Churn"]) == {0, 1}


def test_one_hot_groups_sum_to_one(v2):
    for prefix in ["gender_", "InternetService_", "Contract_", "payment_method_"]:
        cols = [c for c in v2.columns if c.startswith(prefix)]
        assert (v2[cols].sum(axis=1) == 1).all(), prefix

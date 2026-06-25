import pandas as pd
import pytest

from app.api.v1.endpoints.analytics import (
    FUNNEL_ORDER,
    VALID_STATUSES,
    build_data_quality,
    filter_statuses,
    flag_duplicates,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


SAMPLE_ROWS = [
    {"rm_tran_no": 1, "rm_job_status": "Applicant",      "rm_encode_date": "2025-01-01", "admin_condate": None},
    {"rm_tran_no": 2, "rm_job_status": "For Medical",     "rm_encode_date": "2025-01-05", "admin_condate": None},
    {"rm_tran_no": 3, "rm_job_status": "For Onboarding",  "rm_encode_date": "2025-01-10", "admin_condate": None},
    {"rm_tran_no": 4, "rm_job_status": "Onboarded",       "rm_encode_date": "2025-01-03", "admin_condate": "2025-01-20"},
    {"rm_tran_no": 5, "rm_job_status": "Failed Drug test", "rm_encode_date": "2025-01-12", "admin_condate": None},
    {"rm_tran_no": 6, "rm_job_status": "-",                "rm_encode_date": "2025-01-15", "admin_condate": None},
    {"rm_tran_no": 7, "rm_job_status": "Archive",          "rm_encode_date": "2025-01-16", "admin_condate": None},
    {"rm_tran_no": 8, "rm_job_status": "Unknown",          "rm_encode_date": "2025-01-17", "admin_condate": None},
]


# ---------------------------------------------------------------------------
# filter_statuses
# ---------------------------------------------------------------------------

class TestFilterStatuses:
    def test_valid_statuses_pass(self):
        df = make_df(SAMPLE_ROWS)
        result = filter_statuses(df)
        assert set(result["rm_job_status"].unique()) <= VALID_STATUSES

    def test_dash_excluded(self):
        df = make_df(SAMPLE_ROWS)
        result = filter_statuses(df)
        assert "-" not in result["rm_job_status"].values

    def test_archive_excluded(self):
        df = make_df(SAMPLE_ROWS)
        result = filter_statuses(df)
        assert "Archive" not in result["rm_job_status"].values

    def test_unknown_status_excluded(self):
        df = make_df(SAMPLE_ROWS)
        result = filter_statuses(df)
        assert "Unknown" not in result["rm_job_status"].values

    def test_correct_count(self):
        df = make_df(SAMPLE_ROWS)
        result = filter_statuses(df)
        # 5 valid rows from SAMPLE_ROWS
        assert len(result) == 5

    def test_empty_df(self):
        result = filter_statuses(pd.DataFrame(columns=["rm_job_status"]))
        assert result.empty


# ---------------------------------------------------------------------------
# flag_duplicates
# ---------------------------------------------------------------------------

class TestFlagDuplicates:
    def test_no_duplicates(self):
        df = make_df([
            {"rm_tran_no": 1, "rm_job_status": "Applicant"},
            {"rm_tran_no": 2, "rm_job_status": "Onboarded"},
        ])
        result = flag_duplicates(df)
        assert not result["_is_duplicate"].any()

    def test_detects_duplicate_tran_no(self):
        df = make_df([
            {"rm_tran_no": 1, "rm_job_status": "Applicant"},
            {"rm_tran_no": 1, "rm_job_status": "For Medical"},
            {"rm_tran_no": 2, "rm_job_status": "Onboarded"},
        ])
        result = flag_duplicates(df)
        assert result[result["rm_tran_no"] == 1]["_is_duplicate"].all()
        assert not result[result["rm_tran_no"] == 2]["_is_duplicate"].any()

    def test_original_df_unchanged(self):
        df = make_df([
            {"rm_tran_no": 1, "rm_job_status": "Applicant"},
            {"rm_tran_no": 1, "rm_job_status": "Onboarded"},
        ])
        flag_duplicates(df)
        assert "_is_duplicate" not in df.columns


# ---------------------------------------------------------------------------
# build_data_quality
# ---------------------------------------------------------------------------

class TestBuildDataQuality:
    def test_no_issues(self):
        df = make_df([
            {"rm_tran_no": 1, "rm_job_status": "Onboarded", "rm_encode_date": "2025-01-01", "admin_condate": "2025-01-20"},
        ])
        result = build_data_quality(df)
        assert result["duplicate_tran_no_count"] == 0

    def test_duplicate_detection(self):
        df = make_df([
            {"rm_tran_no": 1, "rm_job_status": "Applicant",  "rm_encode_date": "2025-01-01", "admin_condate": None},
            {"rm_tran_no": 1, "rm_job_status": "For Medical", "rm_encode_date": "2025-01-02", "admin_condate": None},
        ])
        result = build_data_quality(df)
        assert result["duplicate_tran_no_count"] == 2

    def test_missing_encode_date(self):
        df = make_df([
            {"rm_tran_no": 1, "rm_job_status": "Applicant", "rm_encode_date": None,         "admin_condate": None},
            {"rm_tran_no": 2, "rm_job_status": "Applicant", "rm_encode_date": "2025-01-02", "admin_condate": None},
        ])
        df["rm_encode_date"] = pd.to_datetime(df["rm_encode_date"], errors="coerce")
        result = build_data_quality(df)
        assert result["missing_encode_date"] == 1


# ---------------------------------------------------------------------------
# Funnel order
# ---------------------------------------------------------------------------

class TestFunnelOrder:
    def test_funnel_order_is_correct(self):
        assert FUNNEL_ORDER == ["Applicant", "For Medical", "For Onboarding", "Onboarded"]

    def test_all_funnel_stages_are_valid_statuses(self):
        for stage in FUNNEL_ORDER:
            assert stage in VALID_STATUSES


# ---------------------------------------------------------------------------
# Time metrics (inline logic test — no HTTP)
# ---------------------------------------------------------------------------

class TestTimeMetrics:
    def test_mean_and_median_calculation(self):
        rows = [
            {"rm_tran_no": i, "rm_job_status": "Onboarded",
             "rm_encode_date": pd.Timestamp("2025-01-01"),
             "admin_condate":  pd.Timestamp("2025-01-01") + pd.Timedelta(days=d)}
            for i, d in enumerate([10, 20, 30], start=1)
        ]
        df = pd.DataFrame(rows)
        df["days_to_onboard"] = (df["admin_condate"] - df["rm_encode_date"]).dt.days
        valid = df["days_to_onboard"]

        assert float(valid.mean()) == pytest.approx(20.0)
        assert float(valid.median()) == pytest.approx(20.0)
        assert int(valid.min()) == 10
        assert int(valid.max()) == 30

    def test_negative_days_excluded(self):
        rows = [
            {"rm_encode_date": pd.Timestamp("2025-01-20"), "admin_condate": pd.Timestamp("2025-01-10")},
            {"rm_encode_date": pd.Timestamp("2025-01-01"), "admin_condate": pd.Timestamp("2025-01-11")},
        ]
        df = pd.DataFrame(rows)
        df["days_to_onboard"] = (df["admin_condate"] - df["rm_encode_date"]).dt.days
        valid = df[df["days_to_onboard"] >= 0]["days_to_onboard"]
        assert len(valid) == 1
        assert int(valid.iloc[0]) == 10

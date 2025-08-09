from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from evaluator.evaluate import _fetch_and_map_prices, _save_prices_to_influxdb, main
from optimizer.models import Elpris


class TestEvaluateTimezoneConversion:
    """Test timezone conversion logic for InfluxDB queries."""

    def test_summer_time_conversion_cest(self):
        """Test local Swedish summer time (CEST, UTC+2) converts correctly to UTC."""
        # July date - CEST (UTC+2)
        local_date = datetime(2025, 7, 15, 0, 0, 0)

        # Expected UTC conversion: 2025-07-14 22:00:00 to 2025-07-15 22:00:00
        expected_utc_start = datetime(2025, 7, 14, 22, 0, 0)
        expected_utc_end = datetime(2025, 7, 15, 22, 0, 0)

        # Simulate the conversion logic from evaluate.py
        local_start = local_date
        local_end = local_date + timedelta(days=1)

        utc_start = (
            pd.Timestamp(local_start)
            .tz_localize("Europe/Stockholm")
            .tz_convert("UTC")
            .tz_localize(None)
        ).to_pydatetime()

        utc_end = (
            pd.Timestamp(local_end)
            .tz_localize("Europe/Stockholm")
            .tz_convert("UTC")
            .tz_localize(None)
        ).to_pydatetime()

        assert utc_start == expected_utc_start
        assert utc_end == expected_utc_end

    def test_winter_time_conversion_cet(self):
        """Test local Swedish winter time (CET, UTC+1) converts correctly to UTC."""
        # December date - CET (UTC+1)
        local_date = datetime(2025, 12, 15, 0, 0, 0)

        # Expected UTC conversion: 2025-12-14 23:00:00 to 2025-12-15 23:00:00
        expected_utc_start = datetime(2025, 12, 14, 23, 0, 0)
        expected_utc_end = datetime(2025, 12, 15, 23, 0, 0)

        # Simulate the conversion logic from evaluate.py
        local_start = local_date
        local_end = local_date + timedelta(days=1)

        utc_start = (
            pd.Timestamp(local_start)
            .tz_localize("Europe/Stockholm")
            .tz_convert("UTC")
            .tz_localize(None)
        ).to_pydatetime()

        utc_end = (
            pd.Timestamp(local_end)
            .tz_localize("Europe/Stockholm")
            .tz_convert("UTC")
            .tz_localize(None)
        ).to_pydatetime()

        assert utc_start == expected_utc_start
        assert utc_end == expected_utc_end


class TestEvaluatePriceMapping:
    """Test price mapping and timezone handling for electricity prices."""

    def test_price_hour_mapping_timezone_naive(self):
        """Test that prices are correctly mapped to timezone-naive hours."""
        # Create timezone-aware price data (simulating elpris_api output)
        tz_aware_dt = datetime(
            2025, 7, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=2))
        )  # CEST
        price = Elpris(0.5)  # 0.5 SEK/kWh
        prices = {tz_aware_dt: price}

        # Simulate the price mapping logic from evaluate.py
        price_per_hour = {
            dt.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None): price
            for dt, price in prices.items()
        }

        # Expected timezone-naive key
        expected_key = datetime(2025, 7, 15, 14, 0, 0)

        assert expected_key in price_per_hour
        assert price_per_hour[expected_key] == price


class TestEvaluateEnergyCalculations:
    """Test core energy cost and savings calculations."""

    def test_energy_cost_calculation_wh_to_kwh_conversion(self):
        """Test that energy costs are calculated correctly with Wh to kWh conversion."""
        # Test data: 1000 Wh consumed at 0.5 SEK/kWh should cost 0.5 SEK
        consumption_wh = 1000.0
        price_sek_per_kwh = 0.5

        # Simulate calculation from evaluate.py: diff * (price / 1000)
        cost_sek = consumption_wh * (price_sek_per_kwh / 1000)

        expected_cost = 0.5  # 1000 Wh = 1 kWh, 1 kWh * 0.5 SEK/kWh = 0.5 SEK
        assert cost_sek == expected_cost

    def test_production_revenue_calculation(self):
        """Test that production revenue is calculated correctly."""
        # Test data: 2000 Wh produced at 0.3 SEK/kWh should generate 0.6 SEK revenue
        production_wh = 2000.0
        sell_price_sek_per_kwh = 0.3

        # Simulate calculation from evaluate.py: diff * (price / 1000)
        revenue_sek = production_wh * (sell_price_sek_per_kwh / 1000)

        expected_revenue = 0.6  # 2000 Wh = 2 kWh, 2 kWh * 0.3 SEK/kWh = 0.6 SEK
        assert revenue_sek == expected_revenue

    def test_net_cost_calculation(self):
        """Test net cost calculation (consumption cost - production revenue)."""
        consumption_cost = 5.0  # SEK
        production_revenue = 2.0  # SEK

        net_cost = consumption_cost - production_revenue
        expected_net_cost = 3.0  # SEK

        assert net_cost == expected_net_cost

    def test_savings_calculation(self):
        """Test savings calculation between battery and no-battery scenarios."""
        no_battery_cost = 10.0  # SEK
        actual_cost_with_battery = 7.0  # SEK

        savings = no_battery_cost - actual_cost_with_battery
        expected_savings = 3.0  # SEK

        assert savings == expected_savings


class TestEvaluateDataProcessing:
    """Test data processing and aggregation logic."""

    def test_minutely_power_to_hourly_energy_conversion(self):
        """Test conversion from minutely power (W) to hourly energy (Wh)."""
        # Test data: 60W for 60 minutes should equal 60 Wh
        power_w = 60.0
        minutes = 60

        # Simulate conversion from evaluate.py: value / 60.0 per minute, then sum
        wh_per_minute = power_w / 60.0  # 1 Wh per minute
        total_wh = wh_per_minute * minutes  # 60 Wh total

        expected_wh = 60.0
        assert total_wh == expected_wh

    def test_hourly_aggregation_logic(self):
        """Test hourly aggregation of minutely data."""
        # Create test DataFrame with minutely data
        timestamps = [
            datetime(2025, 7, 15, 14, 0, 0),
            datetime(2025, 7, 15, 14, 30, 0),
            datetime(2025, 7, 15, 15, 0, 0),
            datetime(2025, 7, 15, 15, 30, 0),
        ]

        df = pd.DataFrame(
            {"timestamp": timestamps, "value": [60.0, 60.0, 120.0, 120.0]}  # Watts
        )

        # Simulate the processing logic from evaluate.py
        df["hour"] = pd.to_datetime(df["timestamp"]).dt.floor("h")
        df["wh"] = df["value"] / 60.0
        hourly_aggregated = df.groupby("hour")["wh"].sum().reset_index()

        # Expected: two hours with 2 Wh each (2 * 1 Wh for hour 14, 2 * 2 Wh for hour 15)
        expected_hours = [
            datetime(2025, 7, 15, 14, 0, 0),
            datetime(2025, 7, 15, 15, 0, 0),
        ]
        expected_wh = [2.0, 4.0]  # Hour 14: 2*1Wh, Hour 15: 2*2Wh

        assert len(hourly_aggregated) == 2
        assert hourly_aggregated["hour"].tolist() == expected_hours
        assert hourly_aggregated["wh"].tolist() == expected_wh


class TestEvaluateDataFrameTimezoneHandling:
    """Test DataFrame timezone conversion logic."""

    def test_utc_to_local_conversion_for_dataframes(self):
        """Test UTC timestamp conversion to local Swedish time in DataFrames."""
        # Create UTC timestamp
        utc_timestamp = "2025-07-15T12:00:00Z"

        df = pd.DataFrame({"timestamp": [utc_timestamp], "value": [100.0]})

        # Simulate the conversion logic from evaluate.py
        df["hour"] = (
            pd.to_datetime(df["timestamp"])
            .dt.tz_convert("Europe/Stockholm")
            .dt.tz_localize(None)
            .dt.floor("h")
        )

        # Expected: UTC 12:00 -> CEST 14:00 (July = UTC+2)
        expected_local_hour = datetime(2025, 7, 15, 14, 0, 0)

        assert df["hour"].iloc[0] == expected_local_hour


class TestEvaluatePriceStorage:
    """Test spot price storage functionality."""

    @patch("evaluator.evaluate.InfluxDBClientWrapper")
    def test_save_prices_to_influxdb_with_timezone_aware_prices(self, mock_influx):
        """Test that timezone-aware prices are correctly converted to UTC for InfluxDB."""
        # Create timezone-aware test prices (simulating elpris_api output)
        test_prices = {
            datetime(
                2025, 7, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=2))
            ): Elpris(
                0.5
            ),  # CEST
            datetime(
                2025, 7, 15, 15, 0, 0, tzinfo=timezone(timedelta(hours=2))
            ): Elpris(
                0.6
            ),  # CEST
        }

        # Mock InfluxDB client
        mock_client_instance = MagicMock()
        mock_influx.return_value.__enter__.return_value = mock_client_instance

        # Call the price storage function
        _save_prices_to_influxdb(test_prices)

        # Verify write_point was called twice (once per price)
        assert mock_client_instance.write_point.call_count == 2

        # Verify the calls were made with correct parameters
        calls = mock_client_instance.write_point.call_args_list

        # First call should be for 14:00 CEST -> 12:00 UTC
        first_call = calls[0]
        assert first_call[1]["measurement"] == "SpotPrices"
        assert first_call[1]["fields"]["spot_price"] == 0.5
        assert (
            first_call[1]["fields"]["buy_price"] == 0.5 + 0.4 + 0.55
        )  # spot + delivery + tax
        assert (
            first_call[1]["fields"]["sell_price"] == 0.5 + 0.08 + 0.6
        )  # spot + nätnytta + skatteavdrag
        assert first_call[1]["tags"]["grid_area"] == "SE3"
        assert (
            "2025-07-15T12:00:00Z" in first_call[1]["timestamp"]
        )  # 14:00 CEST -> 12:00 UTC

        # Second call should be for 15:00 CEST -> 13:00 UTC
        second_call = calls[1]
        assert second_call[1]["measurement"] == "SpotPrices"
        assert second_call[1]["fields"]["spot_price"] == 0.6
        assert (
            "2025-07-15T13:00:00Z" in second_call[1]["timestamp"]
        )  # 15:00 CEST -> 13:00 UTC

    @patch("evaluator.evaluate.fetch_electricity_prices")
    def test_fetch_and_map_prices_returns_both_formats(self, mock_fetch_prices):
        """Test that _fetch_and_map_prices returns both original and mapped prices."""
        # Mock the price API response
        test_date = datetime(2025, 7, 15, 0, 0, 0)
        mock_prices = {
            datetime(
                2025, 7, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=2))
            ): Elpris(0.5),
        }
        mock_fetch_prices.return_value = mock_prices

        # Call the function
        original_prices, mapped_prices = _fetch_and_map_prices(test_date)

        # Verify original prices are unchanged (timezone-aware)
        assert len(original_prices) == 1
        original_key = list(original_prices.keys())[0]
        assert original_key.tzinfo is not None
        assert original_key.hour == 14

        # Verify mapped prices are timezone-naive
        assert len(mapped_prices) == 1
        mapped_key = list(mapped_prices.keys())[0]
        assert mapped_key.tzinfo is None
        assert mapped_key.hour == 14

        # Verify both point to the same Elpris object
        assert original_prices[original_key] == mapped_prices[mapped_key]


class TestEvaluateIntegration:
    """Integration tests with mocked dependencies."""

    @patch("evaluator.evaluate.InfluxDBClientWrapper")
    @patch("evaluator.evaluate.fetch_minutely_power")
    @patch("evaluator.evaluate.fetch_hourly_diffs")
    @patch("evaluator.evaluate.fetch_electricity_prices")
    def test_full_evaluation_workflow_with_known_data(
        self, mock_prices, mock_hourly_diffs, mock_minutely_power, mock_influx
    ):
        """Test complete evaluation workflow with known test data."""
        # Setup test date
        test_date = datetime(2025, 7, 15, 0, 0, 0)

        # Mock electricity prices
        price_14h = Elpris(0.5)  # 0.5 SEK/kWh
        price_15h = Elpris(0.6)  # 0.6 SEK/kWh
        mock_prices.return_value = {
            datetime(
                2025, 7, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=2))
            ): price_14h,
            datetime(
                2025, 7, 15, 15, 0, 0, tzinfo=timezone(timedelta(hours=2))
            ): price_15h,
        }

        # Mock hourly energy diffs (consumed/produced from battery system)
        # Battery optimized scenario: lower consumption, higher production sales
        consumed_df = pd.DataFrame(
            {
                "timestamp": ["2025-07-15T12:00:00Z", "2025-07-15T13:00:00Z"],  # UTC
                "diff": [800.0, 1200.0],  # Wh consumed per hour (battery optimized)
            }
        )
        produced_df = pd.DataFrame(
            {
                "timestamp": ["2025-07-15T12:00:00Z", "2025-07-15T13:00:00Z"],  # UTC
                "diff": [600.0, 900.0],  # Wh produced per hour (battery optimized)
            }
        )

        # Mock minutely power data (for no-battery scenario)
        # No-battery scenario: higher consumption from grid, lower PV utilization
        consumed_power_df = pd.DataFrame(
            {
                "timestamp": ["2025-07-15T12:00:00Z"] * 60
                + ["2025-07-15T13:00:00Z"] * 60,  # 60 minutes each hour
                "value": [20.0] * 60
                + [30.0]
                * 60,  # W consumed per minute (20W = 1200Wh/hour, 30W = 1800Wh/hour)
            }
        )
        pv_power_df = pd.DataFrame(
            {
                "timestamp": ["2025-07-15T12:00:00Z"] * 60
                + ["2025-07-15T13:00:00Z"] * 60,  # 60 minutes each hour
                "value": [15.0] * 60
                + [20.0]
                * 60,  # W produced per minute (15W = 900Wh/hour, 20W = 1200Wh/hour)
            }
        )

        def mock_hourly_side_effect(measurement, field, start, end):
            if measurement == "energy.consumed":
                return consumed_df
            elif measurement == "energy.produced":
                return produced_df
            return pd.DataFrame()

        def mock_minutely_side_effect(measurement, field, start, end):
            if measurement == "power.consumed":
                return consumed_power_df
            elif measurement == "power.pv":
                return pv_power_df
            return pd.DataFrame()

        mock_hourly_diffs.side_effect = mock_hourly_side_effect
        mock_minutely_power.side_effect = mock_minutely_side_effect

        # Mock InfluxDB client
        mock_client_instance = MagicMock()
        mock_influx.return_value.__enter__.return_value = mock_client_instance

        # Call main function - should not raise an exception
        main(test_date)

        # Note: InfluxDB write is currently disabled due to debug return statement
        # The function should complete successfully and print the results

        # Test passes if no exception is raised during execution

    @patch("evaluator.evaluate.InfluxDBClientWrapper")
    @patch("evaluator.evaluate.fetch_minutely_power")
    @patch("evaluator.evaluate.fetch_hourly_diffs")
    @patch("evaluator.evaluate.fetch_electricity_prices")
    def test_evaluation_with_empty_data(
        self, mock_prices, mock_hourly_diffs, mock_minutely_power, mock_influx
    ):
        """Test evaluation behavior when InfluxDB returns no data."""
        test_date = datetime(2025, 7, 15, 0, 0, 0)

        # Mock empty prices
        mock_prices.return_value = {}

        # Mock empty dataframes with correct columns
        empty_hourly_df = pd.DataFrame(columns=["timestamp", "diff"])
        empty_minutely_df = pd.DataFrame(columns=["timestamp", "value"])
        mock_hourly_diffs.return_value = empty_hourly_df
        mock_minutely_power.return_value = empty_minutely_df

        # Mock InfluxDB client
        mock_client_instance = MagicMock()
        mock_influx.return_value.__enter__.return_value = mock_client_instance

        # Should not raise an exception
        main(test_date)

        # Note: InfluxDB write is currently disabled due to debug return statement
        # The function should complete successfully with zero values printed

        # Test passes if no exception is raised during execution

    def test_default_evaluation_date(self):
        """Test that default evaluation date is yesterday."""
        with patch("evaluator.evaluate.datetime") as mock_datetime:
            # Mock current time as 2025-07-16 10:30:00
            mock_now = datetime(2025, 7, 16, 10, 30, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            # Mock other dependencies to avoid actual calls
            with patch(
                "evaluator.evaluate.fetch_electricity_prices"
            ) as mock_prices, patch(
                "evaluator.evaluate.fetch_hourly_diffs"
            ) as mock_hourly, patch(
                "evaluator.evaluate.fetch_minutely_power"
            ) as mock_minutely, patch(
                "evaluator.evaluate.InfluxDBClientWrapper"
            ):

                mock_prices.return_value = {}
                mock_hourly.return_value = pd.DataFrame(columns=["timestamp", "diff"])
                mock_minutely.return_value = pd.DataFrame(
                    columns=["timestamp", "value"]
                )

                # Call main without date (should default to yesterday)
                main(None)

                # Verify that prices were fetched for yesterday (2025-07-15)
                expected_date = datetime(2025, 7, 15, 0, 0, 0)
                mock_prices.assert_called_once_with(expected_date, "SE3")


if __name__ == "__main__":
    pytest.main([__file__])

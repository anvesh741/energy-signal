from app.export_static import static_name


def test_static_name_matches_frontend_mapping():
    # frontend/lib/api.ts resolve() must produce the same names
    assert static_name("/api/overview") == "overview.json"
    assert static_name("/api/fuels/storage?region=eia-storage-r31") == "fuels/storage__region_eia-storage-r31.json"
    assert (
        static_name("/api/forecasts/history?series_id=eia-wti&target_kind=daily&horizon=5")
        == "forecasts/history__series_id_eia-wti_target_kind_daily_horizon_5.json"
    )

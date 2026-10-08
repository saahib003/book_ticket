from app.factory import create_app


def test_metrics_endpoint_exposes_http_metrics():
    app = create_app("testing")
    response = app.test_client().get("/health/live")
    assert response.status_code == 200

    metrics = app.test_client().get("/metrics")
    assert metrics.status_code == 200
    assert b"ticket_booking_http_requests_total" in metrics.data

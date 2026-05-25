"""Re-export from services.alerting.anomaly for backwards compatibility."""
from services.alerting.anomaly import (  # noqa: F401
    anomaly_detection_loop,
    run_anomaly_detection_for_customer,
)

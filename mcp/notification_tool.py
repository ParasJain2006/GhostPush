import logging

# Configure logger for NotificationTool
logger = logging.getLogger("GhostPush.NotificationTool")
logger.setLevel(logging.INFO)


class NotificationTool:
    """Tool for logging job events and notifying execution status updates."""

    @staticmethod
    def notify_status(job_id: str, status: str, message: str) -> dict:
        """Logs and formats job status notification."""
        log_entry = {
            "job_id": job_id,
            "status": status,
            "message": message,
        }
        logger.info(f"[{job_id}] [{status}] {message}")
        return log_entry

    @staticmethod
    def success(job_id: str, message: str) -> dict:
        return NotificationTool.notify_status(job_id, "SUCCESS", message)

    @staticmethod
    def warning(job_id: str, message: str) -> dict:
        return NotificationTool.notify_status(job_id, "WARNING", message)

    @staticmethod
    def error(job_id: str, message: str) -> dict:
        return NotificationTool.notify_status(job_id, "ERROR", message)

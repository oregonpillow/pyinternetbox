from internetbox_client.utils.APIClient import APIClient


class Scheduler(APIClient):
    """Scheduled tasks and timer configurations."""

    def complete_schedules(self, schedule_type: str = "WLAN") -> str:
        """Get complete schedules

        Args:
            schedule_type (str): type of schedule to retrieve. E.g. "WLAN", "MST". Default is "WLAN"
        """
        data = {"parameters": {"type": schedule_type}}
        return self.post("/sysbus/Scheduler:getCompleteSchedules", data)

from internetbox_client.utils.APIClient import APIClient


class Temperature(APIClient):
    """Hardware temperature sensors."""

    def sensor(self) -> str:
        """Get temperature sensor data"""
        data = {"parameters": {}}
        return self.post("/sysbus/Temperature/Sensor:get", data)

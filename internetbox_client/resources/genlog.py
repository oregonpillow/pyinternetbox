from internetbox_client.utils.APIClient import APIClient


class GenLog(APIClient):
    """Read general system logs."""

    def next_logs(self, stream: str, nrecords: int) -> str:
        """Get next logs batch

        Args:
            stream (str): log stream name. E.g "cpu"
            nrecords (int): number of log records to retrieve
        """

        data = {"parameters": {"iterator": {"_stream": stream}, "nrecords": nrecords}}
        return self.post("/sysbus/GenLog:nextLogs", data)

    def read_logs(self, nrecords: int) -> str:
        """Read logs

        Args:
            nrecords (int): number of log records to retrieve
        """
        data = {"parameters": {"nrecords": nrecords, "source": "Devices.Device.HGW"}}
        return self.post("/sysbus/GenLog:readLogs", data)

from internetbox_client.utils.APIClient import APIClient


class Phonebook(APIClient):
    """On-device phone book."""

    def all_contacts(self) -> str:
        """Get all phonebook contacts"""
        data = {"parameters": {}}
        return self.post("/sysbus/Phonebook:getAllContacts", data)

    def get_contact(self, id: str) -> str:
        """Get a phonebook contact by its unique ID."""
        data = {"parameters": {"uniqueID": id}}
        return self.post("/sysbus/Phonebook:getContactByUniqueID", data)

    def add_contact(self, contact: dict) -> str:
        """Add a contact to the phonebook. Returns the contact's unique ID.

        e.g.: contact = {"lastRevision": "0001-01-01T00:00:00Z", "name": "N:Hotline", "n": "N:Hotline;;;;", "formattedName": "Hotline", "birthDay": "0001-01-01T00:00:00Z", "title": "", "organisation": "", "url": "", "ringtone": "", "tags": "", "username": "", "vref": "", "etag": "", "syncedWithServer": "OutOfSync", "syncWithServer": False, "addresses": [], "labels": [], "telephoneNumbers": [ { "key": "1", "name": "0800800800", "type": "WORK", "preferred": False } ], "emails": [], "photos": [] }
        """
        data = {"parameters": {"contact": contact}}
        return self.post("/sysbus/Phonebook:addContactAndGenUUID", data)

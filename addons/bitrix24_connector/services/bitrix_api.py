import requests


class BitrixAPI:

    def __init__(self, webhook_url):
        self.webhook_url = webhook_url.rstrip("/") + "/"

    def call(self, method, params=None):

        url = self.webhook_url + method

        response = requests.post(
            url,
            json=params or {},
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise Exception(
                f"Bitrix24: {data.get('error')} - "
                f"{data.get('error_description')}"
            )

        return data

    def test_connection(self):

        return self.call(
            "profile",
            {}
        )

    def get_contacts(self):

        return self.call(
            "crm.contact.list",
            {
                "select": [
                    "ID",
                    "NAME",
                    "LAST_NAME",
                    "SECOND_NAME",
                    "PHONE",
                    "EMAIL",
                ],
                "order": {
                    "ID": "ASC"
                },
            }
        )
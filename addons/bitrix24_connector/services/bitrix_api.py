import requests


class BitrixAPI:

    PAGE_SIZE = 50

    def __init__(self, webhook_url):
        self.webhook_url = webhook_url.rstrip("/") + "/"

    def call(self, method, params=None):

        url = self.webhook_url + method

        try:

            response = requests.post(
                url,
                json=params or {},
                timeout=30,
            )

        except requests.exceptions.RequestException as error:

            raise Exception(
                f"Bitrix24: no se pudo conectar "
                f"({error.__class__.__name__})."
            )

        try:

            data = response.json()

        except ValueError:

            data = None

        if data is None:

            raise Exception(
                f"Bitrix24: error HTTP "
                f"{response.status_code} "
                f"al llamar a {method}."
            )

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

        contacts = []
        start = 0

        while True:

            data = self.call(
                "crm.contact.list",
                {
                    "select": [
                        "ID",
                        "NAME",
                        "LAST_NAME",
                        "SECOND_NAME",
                        "PHONE",
                        "EMAIL",
                        "DATE_MODIFY",
                    ],
                    "order": {
                        "ID": "ASC"
                    },
                    "start": start,
                }
            )

            batch = data.get("result") or []

            contacts.extend(batch)

            if len(batch) < self.PAGE_SIZE:
                break

            start = data.get("next") or (
                start + self.PAGE_SIZE
            )

        return contacts

    def create_contact(self, values):

        return self.call(
            "crm.contact.add",
            {
                "fields": values
            }
        ).get("result")

    def update_contact(self, bitrix_id, values):

        return self.call(
            "crm.contact.update",
            {
                "id": bitrix_id,
                "fields": values,
            }
        )
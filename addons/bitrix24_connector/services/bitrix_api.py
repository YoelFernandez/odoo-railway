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

    def get_contacts(self, since=None):

        params = {
            "select": [
                "ID",
                "NAME",
                "LAST_NAME",
                "SECOND_NAME",
                "PHONE",
                "EMAIL",
                "POST",
                "ADDRESS",
                "ADDRESS_CITY",
                "ADDRESS_POSTAL_CODE",
                "ADDRESS_COUNTRY",
                "DATE_MODIFY",
            ],
            "order": {
                "ID": "ASC"
            },
        }

        if since:

            params["filter"] = {
                ">DATE_MODIFY": since.strftime(
                    "%Y-%m-%dT%H:%M:%S+00:00"
                )
            }

        contacts = []
        start = 0

        while True:

            params["start"] = start

            data = self.call(
                "crm.contact.list",
                params,
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

    def get_companies(self, since=None):

        params = {
            "select": [
                "ID",
                "TITLE",
                "DATE_MODIFY",
            ],
            "order": {
                "ID": "ASC"
            },
        }

        if since:

            params["filter"] = {
                ">DATE_MODIFY": since.strftime(
                    "%Y-%m-%dT%H:%M:%S+00:00"
                )
            }

        companies = []
        start = 0

        while True:

            params["start"] = start

            data = self.call(
                "crm.company.list",
                params,
            )

            batch = data.get("result") or []

            companies.extend(batch)

            if len(batch) < self.PAGE_SIZE:
                break

            start = data.get("next") or (
                start + self.PAGE_SIZE
            )

        return companies

    def create_company(self, values):

        return self.call(
            "crm.company.add",
            {
                "fields": values
            }
        ).get("result")

    def update_company(self, bitrix_id, values):

        return self.call(
            "crm.company.update",
            {
                "id": bitrix_id,
                "fields": values,
            }
        )

    def get_deals(self, since=None):

        params = {
            "select": [
                "ID",
                "TITLE",
                "OPPORTUNITY",
                "DATE_MODIFY",
            ],
            "order": {
                "ID": "ASC"
            },
        }

        if since:

            params["filter"] = {
                ">DATE_MODIFY": since.strftime(
                    "%Y-%m-%dT%H:%M:%S+00:00"
                )
            }

        deals = []
        start = 0

        while True:

            params["start"] = start

            data = self.call(
                "crm.deal.list",
                params,
            )

            batch = data.get("result") or []

            deals.extend(batch)

            if len(batch) < self.PAGE_SIZE:
                break

            start = data.get("next") or (
                start + self.PAGE_SIZE
            )

        return deals

    def get_deal(self, deal_id):

        return self.call(
            "crm.deal.get",
            {
                "id": deal_id,
                "select": [
                    "ID",
                    "TITLE",
                    "OPPORTUNITY",
                    "CURRENCY_ID",
                    "COMPANY_ID",
                    "CONTACT_ID",
                    "STAGE_ID",
                    "STAGE_SEMANTIC",
                    "DATE_CREATE",
                    "DATE_MODIFY",
                    "CLOSEDATE",
                    "OPPORTUNITY",
                    "TYPE_ID",
                    "BEGINDATE",
                ],
            },
        ).get("result")

    def get_deal_fields(self):

        data = self.call(
            "crm.deal.fields",
            {
                "explain": True,
                "filter": {
                    "attr": "custom",
                },
            },
        )

        return data.get("result") or {}

    def update_deal(self, deal_id, values):

        return self.call(
            "crm.deal.update",
            {
                "id": deal_id,
                "fields": values,
            },
        )
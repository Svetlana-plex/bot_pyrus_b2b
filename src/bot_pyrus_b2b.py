import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class PyrusB2BBot:
    def __init__(self):
        self.pyrus_api_key = os.getenv("PYRUS_API_KEY")
        self.pyrus_form_id = os.getenv("PYRUS_FORM_ID")
        self.pyrus_base_url = "https://pyrus.com/api/v4"
        self.b2b_url = os.getenv("B2B_CENTER_URL")
        self.b2b_auth = (os.getenv("B2B_CENTER_USERNAME"), os.getenv("B2B_CENTER_PASSWORD"))
        self.pyrus_headers = {
            "Authorization": f"Bearer {self.pyrus_api_key}",
            "Content-Type": "application/json"
        }

    def get_pyrus_purchase(self, pyrus_task_id):
        """Получить данные о закупке из Pyrus по ID задачи."""
        response = requests.get(
            f"{self.pyrus_base_url}/tasks/{pyrus_task_id}",
            headers=self.pyrus_headers
        )
        if response.status_code == 200:
            return response.json()["task"]
        else:
            raise Exception(f"Ошибка получения задачи Pyrus: {response.status_code}")

    def check_purchase_in_b2b(self, purchase_id):
        """Проверить, существует ли закупка с указанным ID в B2B-Center."""
        response = requests.get(
            f"{self.b2b_url}/purchases/{purchase_id}",
            auth=self.b2b_auth
        )
        return response.status_code == 200

    def create_purchase_in_b2b(self, purchase_data):
        """Создать закупку в B2B-Center."""
        payload = {
            "name": purchase_data["subject"],
            "b2b_id": purchase_data.get("b2b_id"),
            "lots": purchase_data.get("lots", []),
            "documents": purchase_data.get("documents", []),
            "deadline": purchase_data.get("deadline"),
            "status": "active"
        }
        response = requests.post(
            f"{self.b2b_url}/purchases",
            json=payload,
            auth=self.b2b_auth
        )
        if response.status_code == 201:
            return response.json()["id"]
        else:
            raise Exception(f"Ошибка создания закупки в B2B: {response.status_code}")

    def get_b2b_participants(self, purchase_id):
        """Получить список участников (контрагентов) закупки из B2B-Center."""
        response = requests.get(
            f"{self.b2b_url}/purchases/{purchase_id}/participants",
            auth=self.b2b_auth
        )
        if response.status_code == 200:
            return response.json()["participants"]
        else:
            raise Exception(f"Ошибка получения участников: {response.status_code}")

    def sync_purchase(self, pyrus_task_id):
        """Синхронизировать закупку между Pyrus и B2B-Center."""
        # 1. Получаем данные о закупке из Pyrus
        pyrus_purchase = self.get_pyrus_purchase(pyrus_task_id)
        purchase_id = pyrus_purchase.get("custom_fields", {}).get("purchase_id")  # предполагаем, что ID закупки хранится в кастомном поле

        # 2. Проверяем, существует ли закупка в B2B-Center
        if self.check_purchase_in_b2b(purchase_id):
            print(f"Закупка {purchase_id} уже существует в B2B-Center. Загружаем данные по участникам.")
            participants = self.get_b2b_participants(purchase_id)
            print(f"Участники закупки: {[p['name'] for p in participants]}")
        else:
            print(f"Закупка {purchase_id} не найдена в B2B-Center. Создаём...")
            # Формируем данные для создания закупки (используем поля из Pyrus)
            purchase_data = {
                "subject": pyrus_purchase["subject"],
                "b2b_id": pyrus_purchase.get("b2b_id"),
                "lots": self.extract_lots(pyrus_purchase),
                "documents": self.extract_documents(pyrus_purchase),
                "deadline": pyrus_purchase.get("deadline")
            }
            b2b_purchase_id = self.create_purchase_in_b2b(purchase_data)
            print(f"Закупка создана в B2B-Center. ID: {b2b_purchase_id}")

    def extract_lots(self, pyrus_purchase):
        """Извлечь данные о лотах из задачи Pyrus."""
        lots = []
        for field in pyrus_purchase["fields"]:
            if "lot" in field["id"]:
                lot = {
                    "name": field["value"],
                    "quantity": field.get("quantity"),
                    "price": field.get("price")
                }
                lots.append(lot)
        return lots

    def extract_documents(self, pyrus_purchase):
        """Извлечь данные о документах из задачи Pyrus."""
        documents = []
        for attachment in pyrus_purchase.get("attachments", []):
            doc = {
                "name": attachment["name"],
                "url": attachment["url"],
                "type": attachment.get("type")
            }
            documents.append(doc)
        return documents

    def run(self, pyrus_task_id):
        """Запуск синхронизации для указанной задачи Pyrus."""
        print(f"[{datetime.now()}] Начало синхронизации для задачи Pyrus ID: {pyrus_task_id}")
        self.sync_purchase(pyrus_task_id)
        print(f"[{datetime.now()}] Синхронизация завершена.")


# Запуск бота
if __name__ == "__main__":
    bot = PyrusB2BBot()
    bot.run(174)  # замените на ID задачи Pyrus

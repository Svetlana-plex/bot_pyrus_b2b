import os
import requests
import json
import hmac
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

class PyrusB2BBot:
    def __init__(self):
        self.pyrus_api_key = os.getenv("PYRUS_API_KEY")
        self.pyrus_form_id = os.getenv("PYRUS_FORM_ID")
        self.pyrus_base_url = os.getenv("PYRUS_BASE_URL")
        self.b2b_url = os.getenv("B2B_CENTER_URL")
        self.b2b_auth = (os.getenv("B2B_CENTER_USERNAME"), os.getenv("B2B_CENTER_PASSWORD"))
        self.pyrus_headers = {
            "Authorization": f"Bearer {self.pyrus_api_key}",
            "Content-Type": "application/json"
        }
        self.app = Flask(__name__)
        self._setup_routes()

    def _is_signature_correct(self, message, secret, signature):
        """Проверяет корректность HMAC-подписи (SHA1)."""
        secret = str.encode(secret)
        if isinstance(message, str):
            message = message.encode('utf-8')
        digest = hmac.new(secret, msg=message, digestmod=hashlib.sha1).hexdigest()
        return hmac.compare_digest(digest, signature.lower())

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

    def _setup_routes(self):
        @self.app.route('/create-b2b/<purchase_id>', methods=['POST'])
        def create_b2b_purchase(purchase_id):
            try:
                request_body = request.get_data()
                signature = request.headers.get('X-Pyrus-Signature')

                if not self.verify_webhook(request_body, signature):
                    return jsonify({"error": "Invalid signature"}), 401

                if self.check_purchase_in_b2b(purchase_id):
                    return jsonify({
                        "status": "already_exists",
                        "purchase_id": purchase_id
                    }), 200

                task_id = self._find_task_by_purchase_id(purchase_id)
                if not task_id:
                    return jsonify({
                        "error": f"Задача с purchase_id={purchase_id} не найдена в Pyrus"
                    }), 404

                pyrus_purchase = self.get_pyrus_purchase(task_id)
                purchase_data = {
                    "subject": pyrus_purchase["subject"],
                    "b2b_id": pyrus_purchase.get("b2b_id"),
                    "lots": self.extract_lots(pyrus_purchase),
                    "documents": self.extract_documents(pyrus_purchase),
                    "deadline": pyrus_purchase.get("deadline")
                }

                b2b_purchase_id = self.create_purchase_in_b2b(purchase_data)
                return jsonify({
                    "status": "created",
                    "purchase_id": b2b_purchase_id
                }), 201

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/load-participants/<purchase_id>', methods=['GET'])
        def load_b2b_participants(purchase_id):
            try:
                # Если данные раньше приходили в теле POST-запроса (request.get_data()),
                # то теперь их нужно получать из параметров GET-запроса (request.args)
                request_body = request.args  # или request.args.to_dict() для словаря
                signature = request.headers.get('X-Pyrus-Signature')

                if not self.verify_webhook(request_body, signature):
                    return jsonify({"error": "Invalid signature"}), 401

                participants = self.get_b2b_participants(purchase_id)

                return jsonify({
                    "status": "success",
                    "purchase_id": purchase_id,
                    "participants_count": len(participants),
                    "participants": participants
                }), 200

            except Exception as e:
                return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    bot = PyrusB2BBot()
    # Запускаем сервер на порту 5000
    bot.app.run(host='0.0.0.0', port=5000, debug=False)

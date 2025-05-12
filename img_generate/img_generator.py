import json
import time
import base64
import requests

from img_generate.config import API_KEY, SECRET_KEY


class FusionBrainAPI:
    def __init__(self, base_url="https://api-key.fusionbrain.ai/"):
        self.URL = base_url
        self.AUTH_HEADERS = {
            'X-Key': f'Key {API_KEY}',
            'X-Secret': f'Secret {SECRET_KEY}',
        }

    def get_pipeline(self):
        response = requests.get(self.URL + 'key/api/v1/pipelines', headers=self.AUTH_HEADERS)
        response.raise_for_status()
        return response.json()[0]['id']

    def generate(
            self,
            post_text,
            user_prompt,
            pipeline_id,
            width=512,
            height=512,
            images=1
    ):
        instruction = (
            "Сгенерируй изображение для поста в телеграмм, "
            "которое подходит по смыслу. Вот сам текст поста: "
            f"{post_text}.\n"
        )
        if user_prompt:
            instruction += f"Обязательно учти следующие требования: {user_prompt}"
        print(f"Пртом для изображения {instruction}")
        full_prompt = instruction

        params = {
            "type": "GENERATE",
            "numImages": images,
            "width": width,
            "height": height,
            "generateParams": {
                "query": full_prompt
            }
        }

        data = {
            'pipeline_id': (None, pipeline_id),
            'params': (None, json.dumps(params), 'application/json')
        }

        response = requests.post(self.URL + 'key/api/v1/pipeline/run',
                                 headers=self.AUTH_HEADERS, files=data)
        response.raise_for_status()
        return response.json()['uuid']

    def check_generation(self, uuid, attempts=10, delay=3):
        while attempts > 0:
            response = requests.get(self.URL + f'key/api/v1/pipeline/status/{uuid}', headers=self.AUTH_HEADERS)
            response.raise_for_status()
            data = response.json()
            if data['status'] == 'DONE':
                if data['result']['censored']:
                    raise RuntimeError("⚠️ Картинка отклонена цензурой.")
                return data['result']['files']
            elif data['status'] == 'FAIL':
                raise RuntimeError("❌ Генерация не удалась.")
            time.sleep(delay)
            attempts -= 1
        raise TimeoutError("🕒 Истекло время ожидания")

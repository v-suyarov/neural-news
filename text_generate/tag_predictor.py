from concurrent.futures import ThreadPoolExecutor
import requests


class AsyncTagPredictClient:
    def __init__(self, url="http://localhost:5000/predict_tags", max_workers=5):
        self.url = url
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def predict_tags(self, text: str, available_tags: list[str]) -> list[str]:
        """
        Синхронный запрос к FastAPI-серверу для предсказания тегов.
        Может бросить исключение.
        """
        response = requests.post(self.url, json={
            "text": text,
            "available_tags": available_tags
        })
        response.raise_for_status()
        return response.json().get("tags", [])


tag_predict_client = AsyncTagPredictClient()

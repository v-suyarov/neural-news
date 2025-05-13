from concurrent.futures import ThreadPoolExecutor
import requests


class AsyncRewriteClient:
    def __init__(self, url="http://localhost:5000/rewrite", max_workers=5):
        self.url = url
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def rewrite(self, text: str, prompt: str) -> str:
        """
        Синхронный запрос к модели. Может бросить исключение.
        """
        response = requests.post(self.url, json={"text": text, "prompt": prompt})
        response.raise_for_status()
        return response.json()["rewritten"]


rewrite_client = AsyncRewriteClient()

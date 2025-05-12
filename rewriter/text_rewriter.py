from concurrent.futures import ThreadPoolExecutor
import requests


class AsyncRewriteClient:
    def __init__(self, url="http://localhost:5000/rewrite", max_workers=5):
        self.url = url
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def rewrite(self, text: str, prompt: str, callback):
        def task():
            try:
                response = requests.post(self.url, json={"text": text, "prompt": prompt})
                if response.status_code == 200:
                    rewritten = response.json()["rewritten"]
                    callback(rewritten)
                else:
                    callback(f"[Ошибка {response.status_code}] {response.text}")
            except Exception as e:
                callback(f"[Исключение] {e}")

        self.executor.submit(task)


rewrite_client = AsyncRewriteClient()

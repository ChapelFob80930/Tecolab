import json
import random
from locust import HttpUser, task, between, events

ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

_TOKEN = None
_THREAD_IDS = []
_FINISHED_COURSE_IDS = []

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global _TOKEN, _THREAD_IDS, _FINISHED_COURSE_IDS

    with open("seeded_ids.json") as f:
        seeded = json.load(f)

    _THREAD_IDS = [s["thread_id"] for s in seeded]
    _FINISHED_COURSE_IDS = [s["course_id"] for s in seeded if s["finished"]]

    if not _FINISHED_COURSE_IDS:
        print("WARNING: no finished courses found — /result requests will have nothing to hit.")

    import requests
    resp = requests.post(
        f"{environment.host}/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    resp.raise_for_status()
    _TOKEN = resp.json()["access_token"]
    print(f"Logged in. Token: {_TOKEN[:20]}...")



class TecolabUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        self.client.headers.update({"Authorization": f"Bearer {_TOKEN}"})

    @task(3)
    def check_status(self):
        thread_id = random.choice(_THREAD_IDS)
        self.client.get(
            f"/course_agent/status/{thread_id}",
            name="/course_agent/status/[thread_id]"
        )

    @task(1)
    def get_result(self):
        course_id = random.choice(_FINISHED_COURSE_IDS)
        self.client.get(
            f"/course_agent/result/{course_id}",
            name="/course_agent/result/[course_id]"
        )
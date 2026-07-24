import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import json

BASE_URL = "http://13.205.96.55"
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"
TIMEOUT = 60

TOPICS = [
    "A beginner course on Python decorators",
    "A beginner course on Docker networking",
    "A beginner course on REST API design",
    "A beginner course on Git branching strategies",
    "A beginner course on SQL indexing"
]

TOPIC_KEYWORDS = {
    "A beginner course on Python decorators": "decorator",
    "A beginner course on Docker networking": "docker",
    "A beginner course on REST API design": "REST",
    "A beginner course on Git branching strategies": "branch",
    "A beginner course on SQL indexing": "index",
}

# Of the above, how many do we drive to FULL completion for /result seeding.
# Each one costs multiple real OpenAI calls (outline + N modules), so keep low.
COMPLETE_COUNT = 2

def login():
    resp = requests.post(
        f"{BASE_URL}/login",
        data = {"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout = TIMEOUT
    )

    # print(resp.status_code)
    # print(resp.text)
    resp.raise_for_status()
    return resp.json()["access_token"]

def start_course(token, topic):
    resp = requests.post(
        f"{BASE_URL}/course_agent/start",
        json = {"human_request" : topic},
        headers = {"Authorization" : f"Bearer {token}"},
        timeout = TIMEOUT
    )

    # print(resp.status_code)
    # print(resp.text)
    resp.raise_for_status()
    return resp.json()

def get_status(token, thread_id):
    resp = requests.get(
        f"{BASE_URL}/course_agent/status/{thread_id}",
        headers ={"Authorization": f"Bearer {token}"},
        timeout = TIMEOUT
    )

    # print(resp.status_code)
    # print(resp.text)
    resp.raise_for_status()
    return resp.json()

def resume(token, thread_id, review_action, user_edit_request=None):
    body = {
        "thread_id": thread_id,
        "review_action": review_action,
        "user_edit_request": user_edit_request or "Approved. Continue."
    }

    resp = requests.post(
        f"{BASE_URL}/course_agent/resume",
        json = body,
        headers = {"Authorization": f"Bearer {token}"},
        timeout = TIMEOUT
    )

    resp.raise_for_status()
    return resp.json()

def drive_to_completion(token, thread_id, max_steps=15):
    for _ in range(max_steps):
        curr_status = get_status(token, thread_id)
        if curr_status["run_status"] == "finished":
            return True
        resume(token, thread_id, review_action="approve")
        time.sleep(1)
    return False

def fire_concurrent_starts(token, topics):
    results = {}
    with ThreadPoolExecutor(max_workers = len(topics)) as pool:
        futures = {pool.submit(start_course, token, topic): topic for topic in topics}
        for future in as_completed(futures):
            topic = futures[future]
            data = future.result()
            results[data["thread_id"]] = {"topic": topic, "start_response": data}
    return results

def verify_no_contamination(token, results):
    contamination_found = False
    for thread_id, info in results.items():
        current_status = get_status(token, thread_id)
        if current_status["thread_id"] != thread_id:
            contamination_found = True
            print(f"MISMATCH: requested {thread_id}, got {current_status['thread_id']}")
        else:
            print(f"OK: thread_id={thread_id} run_status={current_status['run_status']}")

    return not contamination_found

def get_course_result(token, course_id):
    resp = requests.get(
        f"{BASE_URL}/course_agent/result/{course_id}",
        headers = {"Authorization": f"Bearer {token}"},
        timeout = TIMEOUT
    )

    resp.raise_for_status()
    return resp.json()

def verify_content_matches_topic(token, course_id, topic):
    result = get_course_result(token, course_id)
    keyword = TOPIC_KEYWORDS[topic].lower()
    outline_text = result["final_course_outline"].lower()
    return keyword in outline_text

def main():
    token = login()
    print(f"Logged in\n")

    print(f"Firing {len(TOPICS)} concurrent /start calls...")
    results = fire_concurrent_starts(token, TOPICS)
    for thread_id, info in results.items():
        print(f"  started: topic='{info['topic'][:40]}' thread_id={thread_id}")

    print("\nVerifying no cross-thread contamination via /status...")
    passed = verify_no_contamination(token, results)
    if not passed:
        print("*** PART A FAILED — stop and debug before Part B. ***")
        return
    print("\nPart A passed.\n")

    thread_ids = list(results.keys())
    to_complete = thread_ids[:COMPLETE_COUNT]
    seeded = []

    for thread_id in thread_ids:

        info = results[thread_id]
        entry = {
            "thread_id": thread_id,
            "course_id": info["start_response"]["course_id"],
            "finished": False,
        }

        if thread_id in to_complete:
            print(f"Completing {thread_id} ({info['topic'][:40]})...")
            finished = drive_to_completion(token, thread_id)
            entry["finished"] = finished

            if finished:
                content_ok = verify_content_matches_topic(
                    token, entry["course_id"], info["topic"]
                )
                print(f"  finished={finished}, content matches topic={content_ok}")

            else:
                print(f"  finished={finished} (did not complete within max_steps)")

        seeded.append(entry)

    with open("seeded_ids.json", "w") as f:
        json.dump(seeded, f, indent=2)

    print(f"\nWrote seeded_ids.json with {len(seeded)} entries.")

if __name__ == "__main__":
    main()

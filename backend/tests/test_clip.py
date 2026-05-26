import requests
import sys

def test():
    req = {
        "songId": 1,
        "startTime": 0.0,
        "endTime": 5.0
    }
    print(f"Sending request: {req}")
    resp = requests.post("http://localhost:8000/api/v1/generate-clip", json=req)
    print(f"Status code: {resp.status_code}")
    print(f"Response: {resp.text}")

if __name__ == "__main__":
    test()

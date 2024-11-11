import pandas as pd

import requests

video_id = 'pA9S1mTqAwU'
question = 'What is this video about?'
print("video_id: ", video_id)

generate_transcript_url = "http://127.0.0.1:5001/generate_transcript"
question_url = "http://127.0.0.1:5001/question"
feedback_url = "http://127.0.0.1:5001/feedback"

data = {
    "video_id": video_id,
    "conversation_id":"983f8ae6-2a7f-46a0-81f7-29ce75669018",
    "question": question,
    "feedback": 1
}

response = requests.post(feedback_url, json=data)
# print(response.content)

print(response.json())
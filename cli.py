import json
import uuid
import argparse

import requests
import questionary

import pandas as pd


def ask_question(url, question,video_id):
    data = {"video_id":video_id, "question": question}
    response = requests.post(url, json=data)
    return response.json()


def send_feedback(url, conversation_id, feedback):
    feedback_data = {"conversation_id": conversation_id, "feedback": feedback}
    response = requests.post(f"{url}/feedback", json=feedback_data)
    return response.status_code

def generate_transcript(url, video_id):
    data = {"video_id": video_id}
    response = requests.post(f"{url}/generate_transcript", json=feedback_data)
    return response.json()


def main():
    parser = argparse.ArgumentParser(
        description="Interactive CLI app for continuous question answering and feedback"
    )
    args = parser.parse_args()
    video_id = ''
    base_url = "http://localhost:5000"

    print("Welcome to the interactive question-answering app!")
    print("You can exit the program at any time when prompted.")

    while True:
        generate_transcript_prompt = questionary.confirm("Do you want to generate transcript?").ask()
        if generate_transcript_prompt:
            video_id = questionary.text("Enter your video_id:").ask()
            response = generate_transcript(base_url, video_id)
            if response.get('generated'):
                print(f"Transcript generated successfully for video {video_id}")
            else:
                print(f"Transcript for {video_id} already available in {response.get('original_language')}")
        if video_id == '':
            video_id = questionary.text("Enter your video_id:").ask()
        question = questionary.text("Enter your question:").ask()

        response = ask_question(f"{base_url}/question", question, video_id)
        print("\nAnswer:", response.get("answer", "No answer provided"))

        conversation_id = response.get("conversation_id", str(uuid.uuid4()))

        feedback = questionary.select(
            "How would you rate this response?",
            choices=["+1 (Positive)", "-1 (Negative)", "Pass (Skip feedback)"],
        ).ask()

        if feedback != "Pass (Skip feedback)":
            feedback_value = 1 if feedback == "+1 (Positive)" else -1
            status = send_feedback(base_url, conversation_id, feedback_value)
            print(f"Feedback sent. Status code: {status}")
        else:
            print("Feedback skipped.")

        continue_prompt = questionary.confirm("Do you want to continue?").ask()
        if not continue_prompt:
            print("Thank you for using the app. Goodbye!")
            break


if __name__ == "__main__":
    main()
from flask import Flask, request, jsonify
import uuid
from rag import rag
from transcription import generate_chunked_transcript, initialize_and_load_index

import db

app = Flask(__name__)

@app.route('/generate_transcript', methods=['POST'])
def handle_transcript():
    data = request.json
    video_id = data.get('video_id')

    if not video_id:
        return jsonify({"error": "No video provided"}), 400

    # Generate transcript for provided video_id
    chunked_transcript, metadata = generate_chunked_transcript(video_id)
    initialize_and_load_index(chunked_transcript)

    result = {
        "video_id":video_id,
        "language_code" :metadata['language_code'],
        "language" :metadata['language'],
        "generated":metadata['generated']
    }
    if result['generated']:
        db.save_transcript(
            video_id=video_id,
            language_code=metadata['language_code'],
            language=metadata['language']
        )

    return jsonify(result)

@app.route('/question', methods=['POST'])
def handle_question():
    data = request.json
    video_id = data.get('video_id')
    question = data.get('question')

    if not video_id or not question:
        return jsonify({"error": "No question or video provided"}), 400
    
    # Generate a conversation ID
    conversation_id = str(uuid.uuid4())

    # Call the RAG function
    answer_data = rag(question,video_id)

    result =  {
        "conversation_id": conversation_id,
        "video_id": video_id,
        "question": question,
        "answer": answer_data['answer']
    }

    db.save_conversation(
        conversation_id=conversation_id,
        video_id=video_id,
        question=question,
        answer_data=answer_data
    )
    
    return jsonify(result)

@app.route("/feedback", methods=['POST'])
def handle_feedback():
    data = request.json
    conversation_id = data['conversation_id']
    video_id = data['video_id']
    feedback = data['feedback']

    if not video_id or not conversation_id or feedback not in [1, -1]:
        return jsonify({"error": "Invalid input"}), 400

    db.save_feedback(
        conversation_id=conversation_id,
        video_id=video_id,
        feedback=feedback
    )

    results = {"message": f"Feedback received for conversation {conversation_id} in {video_id} video: {feedback} "}

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)
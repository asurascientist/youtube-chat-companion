import os
import pandas as pd
import pickle
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from openai import OpenAI
import json

import db
import minsearch

#Initialize index
index = None

client = OpenAI()

# Directory to save individual transcript files
TRANSCRIPTS_DIR = "../data/transcripts/"

# Ensure the directory exists
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

# Helper function to construct the unique file path for a video transcript
def get_transcript_file_path(video_id):
    filename = f"{video_id}.csv"
    return os.path.join(TRANSCRIPTS_DIR, filename)

def sanitize_video_id(video_id):
    """Convert hyphens in video ID to underscores for file compatibility."""
    return video_id.replace('-', '_')

# Function to check if a transcript file exists for the specified video
def check_existing_transcript(video_id):
    file_path = get_transcript_file_path(video_id)
    
    # Check if the file exists, and if so, return the content as a list of dictionaries
    if os.path.exists(file_path):
        return pd.read_csv(file_path).to_dict(orient='records')
    else:
        return None

# Function to save transcript chunks to a uniquely named CSV file
def save_transcript_chunks(video_id, chunks):
    file_path = get_transcript_file_path(video_id)
    chunks_df = pd.DataFrame(chunks)
    chunks_df.to_csv(file_path, index=False)

def generate_transcript(video_id):
    try:
        # Check available transcripts for the video
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript([t.language_code for t in transcript_list])
        
        language_code = transcript.language_code
        language = transcript.language

        print(f"Pulling transcript for video {video_id} in {language}")
        # Fetch the transcript text
        fetched_transcript = transcript.fetch()
        
    except TranscriptsDisabled:
        return "Subtitles are disabled for this video."
    except NoTranscriptFound:
        return "No transcript available in any language."
    except Exception as e:
        return str(e)

    metadata = {
        "language_code": language_code,
        "language": language,
        "generated": True

    }
    return fetched_transcript, metadata

clean_transcript_prompt = '''
You are a professional editor with expertise in data science. Transform the following podcast transcript into clear, readable text while preserving all original information.

Instructions:

1. Include All Content: Ensure the entire transcript content appears in the final output. Do not omit any key parts.
2. Remove Filler Words and Sounds: Eliminate filler words like "so," "right," "like" when they add no value. Remove any hums, "mhms," or similar sounds.
3. Enhance Sentence Clarity: Rephrase sentences for clarity and grammatical correctness:
- Avoid starting sentences with conjunctions like "And."
- Reframe any sentences that end with "right" into questions if possible.
4. Structure in Paragraphs: Use a clear paragraph structure:
- Logical Breaks: Begin a new paragraph at the end of each thought to enhance readability.
- Paragraph Length: Limit paragraphs to 5-6 sentences for better flow.
5. Major Topic Shifts: For noticeable shifts in topic, insert a separator ~~ between blocks of paragraphs.
6. Subtitles and Conclusion:
- Subtitles: Start each major section with a subtitle summarizing the main topic.
- Conclusion: Add a "Conclusion" subtitle summarizing key points from all sections, not just the final one. Ensure the summary covers main ideas and themes across the transcript.

Output format : 
[
    {{
        "subtitle": "<subtitle>",
        "text": "Sentence 1 of paragraph 1. Sentence 2 of paragraph 1. Sentence 3 of paragraph 1..."
    }},
    {{
        "subtitle": "<subtitle>",
        "text": "Sentence 1 of paragraph 1. Sentence 2 of paragraph 1. Sentence 3 of paragraph 1..."
    }},
    ........
    {{
        "subtitle": "<Conclusion>",
        "text": "A comprehensive summary capturing the main ideas, what is the video about, and themes discussed across all sections."

    }}
]
transcript:
{transcript}
'''

def get_clean_transcript_json_formated(transcript, model='gpt-4o-mini'):
    transcript_chunk = [chunk['text'] for chunk in transcript]
    prompt = clean_transcript_prompt.format(transcript=transcript_chunk)
    response = client.chat.completions.create(
        model = model,
        messages=[{"role":"user", "content": prompt}]
    )

    return response.choices[0].message.content

def generate_chunked_transcript(video_id, max_chunk_length=250, overlap_length=50, min_chunk_length=100):
    
    # Check if the file already exists based on actual language metadata
    existing_transcript = check_existing_transcript(video_id)
    if existing_transcript:
        metadata = {
            "language_code": existing_transcript[0]['language_code'],
            "language": existing_transcript[0]['language'],
            "generated": False
        }
        print(f"Transcript already generated for video ID.")
        return existing_transcript, metadata

    # Generate transcript only if it does not already exist
    raw_transcript, metadata = generate_transcript(video_id)
    if isinstance(raw_transcript, str):  # If the transcript generation returns an error message, return it
        return raw_transcript, metadata
    
    # Generate clean transcript
    clean_transcript = get_clean_transcript_json_formated(raw_transcript)
    transcript = json.loads(clean_transcript)
    # Split the transcript into chunks
    
    chunks = []
    chunk_id = 0

    for section in transcript:
        subtitle = section.get("subtitle", "")
        text = section.get("text", "").replace("\n", " ").replace("\t", " ")
        words = text.split(" ")
        current_chunk = ""

        for word in words:
            if len(current_chunk) + len(word) + 1 > max_chunk_length:
                if current_chunk and len(current_chunk) >= min_chunk_length:
                    overlap_words = current_chunk.split()[-(overlap_length // 5):]
                    overlap_part = " ".join(overlap_words)
                    chunks.append({
                        "video_id": sanitize_video_id(video_id),
                        "language_code": metadata['language_code'],
                        "language": metadata['language'],                        
                        "subtitle": subtitle,
                        "chunk_id": chunk_id,
                        "text_chunk": current_chunk.strip()
                    })
                    chunk_id += 1
                    current_chunk = overlap_part + " " + word
                else:
                    current_chunk += " " + word
            else:
                current_chunk += " " + word

        if current_chunk.strip():
            chunks.append({
                "video_id": sanitize_video_id(video_id),
                "language_code": metadata['language_code'],
                "language": metadata['language'],                        
                "subtitle": subtitle,
                "chunk_id": chunk_id,
                "text_chunk": current_chunk.strip()
            })
            chunk_id += 1
    
    # Save chunks to file using actual `original_language`
    save_transcript_chunks(video_id, chunks)
    print(f"Transcript generated successfully for video ID {video_id}.")

    
    return chunks, metadata



def initialize_and_load_index(chunked_transcript=None):
    """
    Initializes the global index if it is not already an instance of the Index class, and load it if it is already initialized
    
    Returns:
        Index: An instance of the Index class.
    """
    global index
    #initialize index if not initialize
    if not isinstance(index, minsearch.Index):
        index = minsearch.Index(
            text_fields=['subtitle', 'text_chunk'],
            keyword_fields=['video_id', 'chunk_id', 'language_code', 'language']
        )
        if chunked_transcript is not None:
            video_id = chunked_transcript[0]['video_id']

            index.fit(chunked_transcript)
            print(f"{video_id} are indexed successfully.")

    else:
        if chunked_transcript is not None:
            video_id = chunked_transcript[0]['video_id']

            index.fit(chunked_transcript)
            print(f"{video_id} are indexed successfully.")
    return index
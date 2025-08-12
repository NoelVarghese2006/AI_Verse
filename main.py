import sounddevice as sd
import queue, json
from vosk import Model, KaldiRecognizer
import sys, json
from google import genai
from google.genai import types
import pyautogui as pg
import time
import asyncio


q = queue.Queue()

last_partial = ""
pending_partial = None
curr_book = ""
curr_chapter = ""
flag = False
counter = 0
model_index = 0
chat = None

models = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

key_words = ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
             "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
             "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
             "Ezra", "Nehemiah", "Esther", "Job", "Psalms",
             "Proverbs", "Ecclesiastes", "Song of Solomon", "song of songs"
             "Isaiah", "Jeremiah", "Lamentations", "Ezekiel",
             "Daniel", "Hosea", "Joel", "Amos", "Obadiah",
             "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah",
             "Haggai", "Zechariah", "Malachi",
             "Matthew", "Mark", "Luke", "John",
             "Acts of the Apostles", "Romans", "1 Corinthians", "2 Corinthians",
             "Galatians", "Ephesians", "Philippians", "Colossians",
             "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy",
             "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
             "1 John", "2 John", "3 John", "Jude", "Revelation",
             "chapter", "verse"
             ]
             


def callback(indata, frames, time, status):
    q.put(bytes(indata))


def split_bible_book_and_chapter(ref):
    parts = ref.strip().split()
    book = " ".join(parts[:-1])  # everything except last part

    # last part contains chapter and maybe verse (e.g. '1:2')
    chapter_verse = parts[-1]

    # split on colon to separate chapter and verse
    chapter = chapter_verse.split(":")[0]

    return book, chapter

def get_bible_reference(stream):
    global curr_book, curr_chapter, model_index, chat
    if not any(key_word.lower() in stream.lower() for key_word in key_words):
        print("\nNo relevant keywords found in the stream. Ignoring...")
        return
    try:
        response = chat.send_message(stream, 
                                    config=types.GenerateContentConfig(
                                    system_instruction=f"You will be given a stream of words sometimes the words aren't exact due to text-to-speech being a little wonky, return the Bible Reference (only the first verse). Example: Genesis 1:1. If only given partial information like 'sorry verse 8', use chat history. If the stream doesn't contain a verse, ignore it by outputting 'ignored'. The only books that end with 's' are Romans, 1 Corinthians, 2 Corinthians, Galatians, Ephesians, Philippians, Colossians, 1 Thessalonians, 2 Thessalonians, Titus, Hebrews, James, Proverbs, Ecclesiastes, Lamentations, Genesis, Exodus, Leviticus, and Numbers everything else should have no 's' at the end. Current Book is {curr_book} and Current Chapter is {curr_chapter}."),
                                    )
    except Exception as e:
        model_index = (model_index + 1) % len(models)
        chat = client.chats.create(model=models[model_index])  # Start with the first model
        get_bible_reference(stream)
        return
    print(f"\nResponse: {response.text}")
    if(response.text != "ignored"):
        curr_book, curr_chapter = split_bible_book_and_chapter(response.text)
        pg.press("esc")
        pg.click(100, 210)
        pg.hotkey("ctrl", "a")
        pg.press("backspace")
        pg.write(response.text)
        pg.PAUSE = 0.01
        pg.press("enter")
        pg.PAUSE = 0.5


print("Please wait, loading model...")
# Download a Vosk model from: https://alphacephei.com/vosk/models
# "vosk-model-en-us-0.22"   "vosk-model-small-en-us-0.15"
model = Model("vosk-model-small-en-us-0.15")  # Path to unpacked model folder
rec = KaldiRecognizer(model, 16000)

# rec.SetWords(json.dumps(key_words))

client = genai.Client(api_key="YOUR_API_KEY")
# chat = client.chats.create(model="gemini-2.5-flash") # This model has low RPD
chat = client.chats.create(model=models[model_index])  # Start with the first model

with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                       channels=1, callback=callback):
    print("Listening...")


    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            # Final transcription
            result = json.loads(rec.Result())["text"]
            if result.strip():
                # Print final result with newline
                get_bible_reference(result)
            last_partial = ""
            counter = 0
            pending_partial = None
        else:
            # Partial transcription
            partial = json.loads(rec.PartialResult())["partial"]
            if partial != last_partial:
                # Overwrite same line (no newline)
                if pending_partial and pending_partial != partial:
                    counter += 1
                    if counter >= 2 and counter < 3:
                        get_bible_reference(partial)
                        pending_partial = None
                        last_partial = ""

                if "verse" in partial.lower():
                    print("\nVerse detected, processing...")
                    pending_partial = partial
                sys.stdout.write("\r" + partial)
                sys.stdout.flush()
                last_partial = partial

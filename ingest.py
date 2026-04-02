import yt_dlp
from faster_whisper import WhisperModel
import os

def download_audio(youtube_url):
    print(f"Downloading audio from: {youtube_url}")
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'outtmpl': 'temp_audio.%(ext)s',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])
    return "temp_audio.wav"

def transcribe_local(audio_path):
    # 'base' is small and fast. Perfect for CPU testing.
    model_size = "medium"
    print(f"Loading local Whisper model ({model_size})...")
    
    # Running on CPU. 
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    print("Transcribing... this is running 100% on your machine.")
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    transcript = ""
    for segment in segments:
        print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
        transcript += segment.text + " "
        
    return transcript

if __name__ == "__main__":
    url = input("Enter YouTube URL: ")
    try:
        audio_file = download_audio(url)
        full_text = transcribe_local(audio_file)
        
        with open("transcript.txt", "w", encoding="utf-8") as f:
            f.write(full_text)
            
        print("\n[SUCCESS] Transcript saved to transcript.txt")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("\n*** Quick Check: Did you install FFmpeg and add it to your PATH? ***")
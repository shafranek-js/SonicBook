import os
import json
import asyncio
import subprocess
import config

async def extract_chapters_from_file(file_path):
    cmd = [
        config.FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_chapters",
        file_path
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        data = json.loads(stdout.decode('utf-8'))
        
        chapters = []
        if 'chapters' in data:
            for ch in data['chapters']:
                start_time = float(ch.get('start_time', 0))
                end_time = float(ch.get('end_time', 0))
                title = ch.get('tags', {}).get('title', f"Chapter {len(chapters) + 1}")
                
                chapters.append({
                    "title": title,
                    "start": start_time,
                    "end": end_time
                })
        return chapters
    except Exception as e:
        print(f"Error extracting chapters from {file_path}: {e}")
        return []

def sanitize_title(name):
    # Match processor.py logic (no commas)
    import string
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    cleaned = "".join(c for c in name if c in valid_chars and c != ',')
    return " ".join(cleaned.split()).strip(". ")

async def main():
    downloads_dir = config.DOWNLOADS_DIR
    print(f"Scanning directory: {downloads_dir}")
    
    if not os.path.exists(downloads_dir):
        print("Downloads directory does not exist.")
        return

    # Process all media types that might have chapters
    media_files = [f for f in os.listdir(downloads_dir) if f.endswith(('.m4b', '.mp4', '.m4a', '.mp3'))]
    
    for filename in media_files:
        base_name = os.path.splitext(filename)[0]
        json_path = os.path.join(downloads_dir, f"{base_name}.json")
        file_path = os.path.join(downloads_dir, filename)
        
        needs_update = False
        if not os.path.exists(json_path):
            needs_update = True
        else:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    # If chapters are empty or just one placeholder chapter, try to recover
                    if not existing.get("chapters") or len(existing["chapters"]) <= 1:
                        needs_update = True
            except:
                needs_update = True
            
        if not needs_update:
            continue
            
        print(f"Processing {filename}...")
        chapters = await extract_chapters_from_file(file_path)
        
        if chapters:
            meta_data = {
                "title": sanitize_title(base_name),
                "mode": "m4b" if filename.endswith('.m4b') else "mp3",
                "file_name": filename,
                "chapters": chapters
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
            print(f"✅ Recovered chapters for {filename} ({len(chapters)} chapters).")
        else:
            # Only create a stub if it doesn't exist at all
            if not os.path.exists(json_path):
                meta_data = {
                    "title": sanitize_title(base_name),
                    "mode": "mp3",
                    "file_name": filename,
                    "chapters": []
                }
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, ensure_ascii=False, indent=2)
                print(f"📝 Created stub metadata for {filename}.")

if __name__ == "__main__":
    asyncio.run(main())
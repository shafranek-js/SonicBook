import os
import json
import asyncio
import subprocess
import config

async def extract_chapters_from_m4b(file_path):
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

async def main():
    downloads_dir = config.DOWNLOADS_DIR
    print(f"Scanning directory: {downloads_dir}")
    
    if not os.path.exists(downloads_dir):
        print("Downloads directory does not exist.")
        return

    m4b_files = [f for f in os.listdir(downloads_dir) if f.endswith('.m4b')]
    
    for filename in m4b_files:
        base_name = os.path.splitext(filename)[0]
        json_path = os.path.join(downloads_dir, f"{base_name}.json")
        m4b_path = os.path.join(downloads_dir, filename)
        
        if os.path.exists(json_path):
            print(f"Skipping {filename} - JSON already exists.")
            continue
            
        print(f"Processing {filename}...")
        chapters = await extract_chapters_from_m4b(m4b_path)
        
        if chapters:
            meta_data = {
                "title": base_name,
                "mode": "m4b",
                "file_name": filename,
                "chapters": chapters
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
            print(f"✅ Generated JSON for {filename} with {len(chapters)} chapters.")
        else:
            print(f"⚠️ No chapters found in {filename}.")

if __name__ == "__main__":
    asyncio.run(main())
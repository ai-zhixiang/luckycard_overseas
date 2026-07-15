#!/usr/bin/env python3
"""
Stylize pipeline: reads base64 image from stdin → Doubao vision → Seedream → result
Usage: echo "STYLE:watercolor" ; echo "STYLE_PROMPT:..." ; cat image.b64 | python3 pipeline.py
Outputs JSON result to stdout
"""
import json, urllib.request, base64, sys, os, uuid

API_KEY = os.environ.get("ARK_API_KEY")
if not API_KEY:
    print(json.dumps({"status": "error", "message": "ARK_API_KEY not set"}))
    sys.exit(1)
VISION_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
SEEDREAM_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

def api(url, data, timeout=120):
    r = urllib.request.Request(url, json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())

try:
    # Read metadata from first lines
    style = "watercolor"
    style_prompt = ""
    img_b64 = ""
    
    for line in sys.stdin:
        line = line.strip()
        if line.startswith("STYLE:"):
            style = line[6:]
        elif line.startswith("STYLE_PROMPT:"):
            style_prompt = line[13:]
        else:
            img_b64 = line
    
    if not img_b64:
        print(json.dumps({"status": "error", "message": "No image data"}))
        sys.exit(1)
    
    # Step 1: Vision
    vision_data = {
        "model": "doubao-1-5-vision-pro-32k-250115",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": "Describe this image for an AI artist. Focus on: main subject, composition, colors, mood, background. 3-4 sentences."}
        ]}],
        "max_tokens": 300
    }
    vision_resp = api(VISION_URL, vision_data)
    description = vision_resp["choices"][0]["message"]["content"]
    sys.stderr.write(f"VISION: {description[:80]}...\n")
    
    # Step 2: Seedream
    seed_data = {
        "model": "ep-20260525152143-fzpqw",
        "prompt": f"{style_prompt}. Scene: {description}. High quality, detailed.",
        "size": "1920x1920",
        "n": 1
    }
    seed_resp = api(SEEDREAM_URL, seed_data, timeout=180)
    img_url = seed_resp["data"][0]["url"]
    sys.stderr.write(f"SEEDREAM: got URL\n")
    
    # Step 3: Download result to home dir (writable by ubuntu user)
    out_dir = os.path.expanduser("~/stylized_results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"result_{uuid.uuid4().hex[:12]}.jpg")
    urllib.request.urlretrieve(img_url, out_path)
    size = os.path.getsize(out_path)
    sys.stderr.write(f"DOWNLOADED: {size} bytes\n")
    
    # Output result JSON (the server reads this from stdout)
    print(json.dumps({
        "status": "ok",
        "file": out_path,
        "size": size,
        "description": description
    }))
    
except Exception as e:
    print(json.dumps({"status": "error", "message": str(e)}))
    sys.exit(1)

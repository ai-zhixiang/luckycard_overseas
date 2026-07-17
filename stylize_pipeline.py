#!/usr/bin/env python3
"""
Stylize pipeline: reads base64 image from stdin → NSFW check → Doubao vision → Seedream → result
Usage: echo "STYLE:watercolor" ; echo "STYLE_PROMPT:..." ; cat image.b64 | python3 pipeline.py
Outputs JSON result to stdout
"""
import json, urllib.request, base64, sys, os, uuid, io
from PIL import Image

API_KEY = os.environ.get("ARK_API_KEY")
if not API_KEY:
    print(json.dumps({"status": "error", "message": "ARK_API_KEY not set"}))
    sys.exit(1)

VISION_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
SEEDREAM_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

# ── NSFW model (lazy-loaded) ──
_nsfw_model = None
_nsfw_processor = None

def _load_nsfw():
    global _nsfw_model, _nsfw_processor
    if _nsfw_model is not None:
        return
    from transformers import AutoModelForImageClassification, AutoImageProcessor
    model_name = "Falconsai/nsfw_image_detection"
    sys.stderr.write(f"NSFW: loading {model_name}...\n")
    _nsfw_processor = AutoImageProcessor.from_pretrained(model_name)
    _nsfw_model = AutoModelForImageClassification.from_pretrained(model_name)
    sys.stderr.write("NSFW: model ready\n")

def nsfw_check(img: Image.Image) -> tuple[bool, str]:
    """
    Returns (is_safe: bool, label: str)
    safe = True if the image is classified as 'normal'
    """
    try:
        _load_nsfw()
        inputs = _nsfw_processor(images=img, return_tensors="pt")
        outputs = _nsfw_model(**inputs)
        import torch
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        pred_idx = probs.argmax().item()
        label = _nsfw_model.config.id2label[pred_idx]
        score = probs[0][pred_idx].item()
        is_safe = (label == "normal")
        sys.stderr.write(f"NSFW: {label} ({score:.3f})\n")
        return is_safe, label
    except Exception as e:
        sys.stderr.write(f"NSFW: check failed ({e}), allowing pass\n")
        return True, "unknown"

def api(url, data, timeout=120):
    r = urllib.request.Request(url, json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


try:
    # ── Read input ──
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

    # ── Layer 1: Local NSFW model ──
    try:
        raw = base64.b64decode(img_b64)
        pil_img = Image.open(io.BytesIO(raw))
        safe, label = nsfw_check(pil_img)
        if not safe:
            print(json.dumps({
                "status": "error",
                "message": f"Image content not allowed (detected: {label}). Please upload a different photo."
            }))
            sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"NSFW: local check error ({e}), continuing\n")

    # ── Layer 2: Doubao Vision content check ──
    check_data = {
        "model": "doubao-1-5-vision-pro-32k-250115",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": "Is this image safe and appropriate for all audiences? Does it contain nudity, violence, hate speech, or any NSFW content? Answer ONLY with one word: SAFE or UNSAFE."}
        ]}],
        "max_tokens": 10
    }
    try:
        check_resp = api(VISION_URL, check_data)
        check_result = check_resp["choices"][0]["message"]["content"].strip().upper()
        sys.stderr.write(f"DOUBAO CHECK: {check_result}\n")
        if "UNSAFE" in check_result:
            print(json.dumps({
                "status": "error",
                "message": "Image content not suitable. Please upload a different photo."
            }))
            sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"DOUBAO CHECK: error ({e}), continuing\n")

    # ── Step 3: Vision description ──
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

    # ── Step 4: Seedream ──
    seed_data = {
        "model": "ep-20260525152143-fzpqw",
        "prompt": f"{style_prompt}. Scene: {description}. High quality, detailed.",
        "size": "1920x1920",
        "n": 1
    }
    seed_resp = api(SEEDREAM_URL, seed_data, timeout=180)
    img_url = seed_resp["data"][0]["url"]
    sys.stderr.write("SEEDREAM: got URL\n")

    # ── Step 5: Download result ──
    out_dir = os.path.expanduser("~/stylized_results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"result_{uuid.uuid4().hex[:12]}.jpg")
    urllib.request.urlretrieve(img_url, out_path)
    size = os.path.getsize(out_path)
    sys.stderr.write(f"DOWNLOADED: {size} bytes\n")

    print(json.dumps({
        "status": "ok",
        "file": out_path,
        "size": size,
        "description": description
    }))

except Exception as e:
    print(json.dumps({"status": "error", "message": str(e)}))
    sys.stderr.write(f"ERROR: {e}\n")
    sys.exit(1)

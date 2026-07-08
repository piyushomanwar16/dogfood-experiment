#!/usr/bin/env python3
"""Run frontend experiments with 5 Ollama cloud models - saves results for paper."""
import requests, json, re, time
from pathlib import Path

BASE = Path.home() / "Desktop/dogfood-experiment"
MODELS = ["minimax-m3:cloud", "nemotron-3-super:cloud", "kimi-k2.7-code:cloud", "glm-5.2:cloud", "gemma4:cloud"]

VIBE = open(BASE/"prompts"/"vibe_prompt.txt").read()
TECH = open(BASE/"prompts"/"technical_prompt.txt").read()

def query(model, prompt):
    r = requests.post("http://localhost:11434/api/chat", json={
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "stream": False, "options": {"temperature": 0.7, "num_predict": 8192}
    }, timeout=600)
    if r.ok:
        text = r.json().get("message", {}).get("content", "")
        text = re.sub(r'Thinking.*?\.\.\.done thinking\.?\n?', '', text, flags=re.DOTALL).strip()
        return text
    return ""

def extract_html(text):
    for p in [r'```html\s*([\s\S]*?)```', r'<!DOCTYPE html>[\s\S]*?</html>', r'<html[\s>][\s\S]*?</html>']:
        m = re.search(p, text, re.I)
        if m: return m.group(1) if m.lastindex else m.group(0)
    return text if len(text) > 500 else ""

score_checks = {
    "renderer": r'WebGLRenderer',
    "scene": r'new\s+THREE\.Scene\(\)|Scene\(',
    "camera": r'PerspectiveCamera',
    "anim": r'requestAnimationFrame',
    "light": r'AmbientLight|DirectionalLight|HemisphereLight',
    "shadows": r'shadow|castShadow',
    "3d_obj": r'BoxGeometry|SphereGeometry|TorusGeometry',
    "ui": r'<h1|<h2|<button|overlay',
    "resize": r'resize|onresize',
    "controls": r'OrbitControls'
}

def score(html):
    s = {k: 1 if re.search(p, html, re.I) else 0 for k, p in score_checks.items()}
    return s, round(sum(s.values())/len(s)*10, 1)

results = {}
for model in MODELS:
    short = model.split(":")[0]
    results[model] = {}
    
    for ptype, prompt in [("vibe", VIBE), ("technical", TECH)]:
        print(f"\n[{short}] {ptype}...", end=" ", flush=True)
        t0 = time.time()
        text = query(model, prompt)
        html = extract_html(text)
        
        if html and len(html) > 300:
            s, total = score(html)
            path = BASE/"experiments"/"frontend"/f"{short}_{ptype}"
            path.mkdir(parents=True, exist_ok=True)
            (path/"index.html").write_text(html)
            print(f"✓ Score: {total}/10 ({round(time.time()-t0,1)}s)", flush=True)
            results[model][ptype] = {"score": total, "checks": s, "html_len": len(html), "time": round(time.time()-t0,1)}
        else:
            print(f"✗ No valid HTML ({round(time.time()-t0,1)}s)", flush=True)
            results[model][ptype] = {"score": 0, "html_len": len(html), "time": round(time.time()-t0,1)}

out = BASE/"data"/"cloud_frontend_results.json"
out.write_text(json.dumps(results, indent=2))
print(f"\n\nSaved: {out}")
print(json.dumps({m: {k: v.get("score",0) for k,v in r.items()} for m,r in results.items()}, indent=2))

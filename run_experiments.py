#!/usr/bin/env python3
"""
Efficient experiment runner using Ollama HTTP API.
Runs all steps, saves results incrementally so paper can be written in parallel.
"""

import requests, json, os, re, time, sys
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = Path.home() / "Desktop/dogfood-experiment"

MODELS = [
    "minimax-m3:cloud",
    "nemotron-3-super:cloud",
    "kimi-k2.7-code:cloud",
    "glm-5.2:cloud",
    "gemma4:cloud"
]

OLLAMA_URL = "http://localhost:11434/api/generate"

def query_model(model, prompt, system=None):
    full = f"[System: {system}]\n\n{prompt}" if system else prompt
    start = time.time()
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": model, "prompt": full, "stream": False,
            "options": {"temperature": 0.7, "num_predict": 4096}
        }, timeout=600)
        elapsed = time.time() - start
        if r.ok:
            data = r.json()
            text = data.get("response", "")
            return {"text": text, "time": round(elapsed, 2), "success": True,
                    "chars": len(text), "tokens_est": len(text.split())}
        return {"text": "", "time": round(elapsed, 2), "success": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"text": "", "time": round(time.time()-start, 2), "success": False, "error": str(e)}


def extract_html(text):
    patterns = [
        r'```html\s*([\s\S]*?)```',
        r'```\s*([\s\S]*?<!DOCTYPE html>[\s\S]*?)```',
        r'<!DOCTYPE html>[\s\S]*?</html>',
        r'<html[\s>][\s\S]*?</html>',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    return None


def score_frontend(html):
    checks = {
        "WebGLRenderer": r'WebGLRenderer',
        "Scene": r'new\s+THREE\.Scene\(\)|Scene\(\)',
        "Camera": r'PerspectiveCamera',
        "Animation": r'requestAnimationFrame',
        "Lighting": r'AmbientLight|DirectionalLight|HemisphereLight',
        "3D Object": r'BoxGeometry|SphereGeometry|TorusGeometry',
        "Shadows": r'shadow|castShadow',
        "UI Overlay": r'<h1|<h2|<button|overlay',
        "Resize": r'resize|onresize',
        "OrbitControls": r'OrbitControls'
    }
    scores = {}
    for name, pat in checks.items():
        scores[name] = 1 if re.search(pat, html, re.IGNORECASE) else 0
    total = round(sum(scores.values()) / len(scores) * 10, 1)
    return scores, total


def score_debug(html):
    fixes = {
        "renderer_created": bool(re.search(r'new\s+THREE\.WebGLRenderer', html)),
        "shadows_enabled": bool(re.search(r'castShadow\s*=\s*true', html)),
        "renderer_setup": bool(re.search(r'renderer\.setSize|document\.body\.appendChild\(renderer', html)),
        "orbit_controls": bool(re.search(r'controls\.update\(\)', html)),
        "resize_handler": bool(re.search(r'window\.addEventListener\([\'"]resize[\'"]', html)),
        "delta_time": bool(re.search(r'getDelta\(\)|getElapsedTime|delta', html)) and not re.search(r'delta\s*=\s*0', html),
        "rendering_loop": bool(re.search(r'renderer\.render\(scene,\s*camera\)', html)),
        "import_map": bool(re.search(r'importmap', html)),
    }
    fixed_count = sum(1 for v in fixes.values() if v)
    return fixes, fixed_count


def score_api(html):
    checks = {
        "supabase_client": bool(re.search(r'createClient|SupabaseClient', html)),
        "data_insertion": bool(re.search(r'\.insert\(|\.from\([\'"]\w+[\'"]\)\.insert', html)),
        "click_handling": bool(re.search(r'addEventListener|onclick|\.click\(', html)),
        "error_handling": bool(re.search(r'try|catch|console\.error', html)),
        "config": bool(re.search(r'supabaseUrl|SUPABASE_URL|supabaseKey|anon[Kk]ey', html)),
        "page_load_track": bool(re.search(r'DOMContentLoaded|load|pages?[Vv]isit|page[Ll]oad', html)),
    }
    passed = sum(1 for v in checks.values() if v)
    return checks, passed


def count_hallucinations(text):
    """Count potential hallucinated/non-existent APIs and patterns."""
    issues = []
    
    # Non-existent Three.js APIs
    bad_patterns = [
        (r'THREE\.BoxBufferGeometry', 'BoxBufferGeometry removed in r125'),
        (r'THREE\.PlaneBufferGeometry', 'PlaneBufferGeometry removed'),
        (r'THREE\.Geometry', 'THREE.Geometry removed in r125'),
        (r'THREE\.CylinderBufferGeometry', 'BufferGeometry variants removed'),
        (r'CineonToneMapping', 'CineonToneMapping not in three.js'),
        (r'THREE\.RoundedBoxGeometry', 'Not part of core Three.js'),
        (r'FilmicToneMapping', 'Renamed to ACESFilmicToneMapping'),
        (r'cdn\.threejs\.org', 'Non-existent CDN domain'),
        (r'three@latest', 'Unpinned version - unreliable'),
        (r'BloomPass[^e]', 'Non-existent pass name'),
        (r'renderer\.setPixelratio', 'Wrong capitalization'),
        (r'import.*from.*[\'"]three\.js[\'"]', 'Wrong import path'),
        (r'import.*from.*[\'"]three\.min\.js[\'"]', 'Wrong import path'),
        (r'[Ss]upabase\.auth\(\)', 'Deprecated Supabase auth API'),
        (r'supabase\.storage\(\).*upload', 'May not exist in all versions'),
    ]
    
    for pat, desc in bad_patterns:
        if re.search(pat, text):
            issues.append(desc)
    
    # Count syntax errors (unmatched braces etc)
    js_blocks = re.findall(r'<script[^>]*>([\s\S]*?)</script>', text, re.IGNORECASE)
    for js in js_blocks:
        if js.count('{') != js.count('}'):
            issues.append('Unmatched braces in script')
        if js.count('(') != js.count(')'):
            issues.append('Unmatched parentheses in script')
    
    return issues


def run_frontend(model):
    vibe = open(BASE/"prompts"/"vibe_prompt.txt").read()
    tech = open(BASE/"prompts"/"technical_prompt.txt").read()
    results = {}
    
    for ptype, prompt in [("vibe", vibe), ("technical", tech)]:
        print(f"  [{model}] Frontend {ptype}...")
        best_html = None
        best_score = 0
        iterations_data = []
        
        for i in range(1, 4):
            resp = query_model(model, prompt if i == 1 else 
                f"Improve this code. Make the 3D scene work better with proper lighting, shadows, animation. Issues: {issues_text}\n\n{prompt}")
            
            html = extract_html(resp.get("text", ""))
            if not html:
                html = resp.get("text", "")
                if len(html) > 1000:
                    pass
            
            issues = count_hallucinations(resp.get("text", ""))
            issues_text = "; ".join(issues[:3]) if issues else "quality could be improved"
            
            if html and len(html) > 500:
                scores, total = score_frontend(html)
                
                iterations_data.append({
                    "iteration": i, "score": total, "html_length": len(html),
                    "issues_found": len(issues), "response_time": resp['time']
                })
                
                if total > best_score:
                    best_score = total
                    best_html = html
                
                if total >= 8.0:
                    break
            else:
                iterations_data.append({
                    "iteration": i, "score": 0, "html_length": 0,
                    "issues_found": 0, "response_time": resp['time']
                })
        
        # Save best HTML
        short = model.split(":")[0]
        dir_path = BASE/"experiments"/"frontend"/f"{short}_{ptype}"
        dir_path.mkdir(parents=True, exist_ok=True)
        if best_html:
            (dir_path/"index.html").write_text(best_html)
        
        results[ptype] = {
            "model": model, "prompt_type": ptype,
            "iterations": len(iterations_data),
            "best_score": best_score,
            "iterations_detail": iterations_data,
            "has_working_code": best_html is not None
        }
        print(f"    Score: {best_score}/10 in {len(iterations_data)} iters")
    
    return results


def run_debugging(model):
    vibe = open(BASE/"prompts"/"debug_vibe_prompt.txt").read()
    tech = open(BASE/"prompts"/"debug_technical_prompt.txt").read()
    buggy = (BASE/"experiments"/"debugging"/"buggy_source.html").read_text()
    results = {}
    
    for ptype, prompt in [("vibe", vibe), ("technical", tech)]:
        print(f"  [{model}] Debugging {ptype}...")
        full = f"{prompt}\n\nBUGGY CODE:\n```html\n{buggy}\n```\n\nProvide the complete fixed HTML file."
        
        best_fixes = 0
        best_html = None
        iterations_data = []
        
        for i in range(1, 4):
            resp = query_model(model, full)
            html = extract_html(resp.get("text", ""))
            
            if html and len(html) > 500:
                fixes, count = score_debug(html)
                iterations_data.append({
                    "iteration": i, "bugs_fixed": count, "response_time": resp['time']
                })
                
                if count > best_fixes:
                    best_fixes = count
                    best_html = html
                
                if count >= 7:
                    break
                
                missing = [k for k, v in fixes.items() if not v]
                full = f"Still missing these fixes: {', '.join(missing)}. Fix ALL of them. Provide complete HTML."
            else:
                iterations_data.append({
                    "iteration": i, "bugs_fixed": 0, "response_time": resp['time']
                })
        
        short = model.split(":")[0]
        dir_path = BASE/"experiments"/"debugging"/f"{short}_{ptype}"
        dir_path.mkdir(parents=True, exist_ok=True)
        if best_html:
            (dir_path/"index.html").write_text(best_html)
        
        results[ptype] = {
            "model": model, "prompt_type": ptype,
            "iterations": len(iterations_data),
            "best_bugs_fixed": best_fixes,
            "iterations_detail": iterations_data
        }
        print(f"    Bugs fixed: {best_fixes}/8 in {len(iterations_data)} iters")
    
    return results


def run_api(model):
    vibe = open(BASE/"prompts"/"api_vibe_prompt.txt").read()
    tech = open(BASE/"prompts"/"api_technical_prompt.txt").read()
    results = {}
    
    for ptype, prompt in [("vibe", vibe), ("technical", tech)]:
        print(f"  [{model}] API {ptype}...")
        best_score = 0
        iterations_data = []
        
        for i in range(1, 4):
            resp = query_model(model, prompt)
            html = extract_html(resp.get("text", ""))
            
            if html and len(html) > 500:
                checks, passed = score_api(html)
                iterations_data.append({
                    "iteration": i, "api_score": passed, "response_time": resp['time']
                })
                
                if passed > best_score:
                    best_score = passed
                
                if passed >= 5:
                    break
                
                missing = [k for k, v in checks.items() if not v]
                prompt = f"Missing features: {', '.join(missing)}. Add them.\n\n{prompt if i == 1 else 'Complete the Supabase integration properly.'}"
            else:
                iterations_data.append({
                    "iteration": i, "api_score": 0, "response_time": resp['time']
                })
        
        short = model.split(":")[0]
        dir_path = BASE/"experiments"/"api-integration"/f"{short}_{ptype}"
        dir_path.mkdir(parents=True, exist_ok=True)
        if html and len(html) > 500:
            (dir_path/"index.html").write_text(html)
        
        results[ptype] = {
            "model": model, "prompt_type": ptype,
            "iterations": len(iterations_data),
            "best_api_score": best_score,
            "iterations_detail": iterations_data
        }
        print(f"    API score: {best_score}/6 in {len(iterations_data)} iters")
    
    return results


def run_hallucination(model):
    print(f"  [{model}] Hallucination analysis...")
    prompts = [
        open(BASE/"prompts"/"technical_prompt.txt").read(),
        "Create a 3D dog food website with Three.js and Supabase. Include complete code with 3D scene, click tracking, and database integration."
    ]
    
    total_issues = []
    all_responses = []
    
    for i, prompt in enumerate(prompts):
        resp = query_model(model, prompt)
        all_responses.append(resp)
        
        if resp.get("success"):
            text = resp.get("text", "")
            issues = count_hallucinations(text)
            total_issues.extend(issues)
    
    short = model.split(":")[0]
    (BASE/"experiments"/"hallucination").mkdir(parents=True, exist_ok=True)
    result = {
        "model": model,
        "total_hallucinations": len(total_issues),
        "hallucination_list": total_issues,
        "avg_response_time": round(sum(r['time'] for r in all_responses) / len(all_responses), 2),
        "all_text_length": sum(r.get('chars', 0) for r in all_responses)
    }
    print(f"    Hallucinations: {len(total_issues)}")
    return result


def main():
    print("="*60)
    print(f"AI MODEL COMPARISON - Starting at {datetime.now().isoformat()}")
    print(f"Models: {MODELS}")
    print("="*60)
    
    all_results = {}
    
    # Create buggy source first
    buggy = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Dog Food</title>
<style>
body{margin:0;overflow:hidden;font-family:Georgia,serif}
#overlay{position:absolute;top:0;left:0;width:100%;height:100%;z-index:10;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none}
#overlay h1{color:#2C1810;font-size:2.5rem;text-shadow:2px 2px 4px rgba(0,0,0,0.3)}
#overlay p{color:#5C3A2E;font-size:1.2rem}
#overlay button{pointer-events:auto;padding:12px 32px;font-size:1.1rem;border:none;border-radius:25px;background:linear-gradient(135deg,#DAA520,#8B4513);color:#fff;cursor:pointer}
</style></head><body>
<div id=overlay><h1>PREMIUM DOG FOOD</h1><p>Crafted with love. Backed by science.</p><button onclick="console.log('clicked')">Shop Now</button></div>
<script type=importmap>{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
<script type=module>
import*as THREE from'three';import{OrbitControls}from'three/addons/controls/OrbitControls.js'
const scene=new THREE.Scene();scene.background=new THREE.Color(0x87CEEB)
const camera=new THREE.PerspectiveCamera(45,window.innerWidth/window.innerHeight,0.1,1000)
camera.position.set(0,2,8)
// BUG: No renderer created
const al=new THREE.AmbientLight(0x404040);scene.add(al)
const dl=new THREE.DirectionalLight(0xffffff,1);dl.position.set(5,10,7);scene.add(dl)
// BUG: No shadow
const bg=new THREE.BoxGeometry(1.5,2.2,0.8);const bm=new THREE.MeshStandardMaterial({color:0x8B4513})
const bag=new THREE.Mesh(bg,bm);scene.add(bag)
// BUG: No animation, no kibble
function animate(){requestAnimationFrame(animate);bag.rotation.y+=0.01}
animate()
// BUG: No render call, no resize handler
</script></body></html>"""
    
    (BASE/"experiments"/"debugging"/"buggy_source.html").write_text(buggy)
    
    # Run experiments sequentially (GPU shared)
    print("\n--- STEP 1: FRONTEND DEVELOPMENT ---")
    fe = {}
    for m in MODELS:
        fe[m] = run_frontend(m)
        # Save intermediate
        with open(BASE/"data"/"partial_frontend.json", "w") as f:
            json.dump(fe, f, indent=2, default=str)
    all_results["frontend"] = fe
    
    print("\n--- STEP 2: DEBUGGING ---")
    db = {}
    for m in MODELS:
        db[m] = run_debugging(m)
        with open(BASE/"data"/"partial_debugging.json", "w") as f:
            json.dump(db, f, indent=2, default=str)
    all_results["debugging"] = db
    
    print("\n--- STEP 3: API INTEGRATION ---")
    api = {}
    for m in MODELS:
        api[m] = run_api(m)
        with open(BASE/"data"/"partial_api.json", "w") as f:
            json.dump(api, f, indent=2, default=str)
    all_results["api"] = api
    
    print("\n--- STEP 4: HALLUCINATION ANALYSIS ---")
    hal = {}
    for m in MODELS:
        hal[m] = run_hallucination(m)
    all_results["hallucination"] = hal
    
    # Final save
    fp = BASE/"data"/f"full_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fp, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print(f"ALL DONE. Results saved to {fp}")
    print("="*60)

if __name__ == "__main__":
    main()

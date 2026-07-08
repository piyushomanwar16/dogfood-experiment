#!/usr/bin/env python3
"""
AI Model Comparison Experiment Runner
Compares local LLMs across: Frontend Dev, Debugging, API Integration, Hallucination
"""

import subprocess, json, os, time, re, shutil
from datetime import datetime
from pathlib import Path

BASE = Path.home() / "Desktop/dogfood-experiment"
MODELS = [
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "deepseek-r1:14b",
    "gemma3:12b"
]
PROMPT_TYPES = ["vibe", "technical"]

results = {}

def query_model(model, prompt, system=None, max_tokens=4096):
    """Query an Ollama model and return response text + timing."""
    cmd = ["ollama", "run", model]
    full_prompt = prompt
    if system:
        full_prompt = f"[System: {system}]\n\n{prompt}"
    
    start = time.time()
    try:
        result = subprocess.run(
            cmd, input=full_prompt.encode(), capture_output=True, timeout=300
        )
        elapsed = time.time() - start
        response = result.stdout.decode().strip()
        return {
            "text": response,
            "time": round(elapsed, 2),
            "success": True,
            "chars": len(response),
            "tokens_est": len(response.split())
        }
    except subprocess.TimeoutExpired:
        return {"text": "", "time": 300, "success": False, "chars": 0, "tokens_est": 0, "error": "timeout"}
    except Exception as e:
        return {"text": "", "time": time.time()-start, "success": False, "chars": 0, "tokens_est": 0, "error": str(e)}


def extract_html(text):
    """Extract HTML code block from model response."""
    patterns = [
        r'```html\s*([\s\S]*?)```',
        r'```\s*([\s\S]*?<!DOCTYPE html>[\s\S]*?)```',
        r'<!DOCTYPE html>[\s\S]*?</html>',
        r'<html>[\s\S]*?</html>',
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return text


def count_html_issues(html):
    """Count potential issues/hallucinations in HTML output."""
    issues = 0
    details = []
    
    # Check for non-existent CDN URLs
    fake_cdns = [
        r'threejs\.org', r'cdn\.threejs\.org', 
        r'unpkg\.com/three@[0-9]+\.[0-9]+\.[0-9]+',
        r'cdnjs\.cloudflare\.com/ajax/libs/three\.js'
    ]
    for cdn in fake_cdns:
        if re.search(cdn, html):
            issues += 1
            details.append(f"CDN: {cdn}")
    
    # Check for syntax errors (basic)
    script_tags = re.findall(r'<script>([\s\S]*?)</script>', html, re.IGNORECASE)
    script_src = re.findall(r'<script src="([^"]+)"', html)
    js_code = ' '.join(script_tags)
    
    # Missing imports
    if 'import' in js_code and 'type="module"' not in html:
        issues += 1
        details.append("ES module import without type=module")
    
    # Unmatched braces (basic JS check)
    braces = js_code.count('{') - js_code.count('}')
    parens = js_code.count('(') - js_code.count(')')
    if abs(braces) > 2 or abs(parens) > 2:
        issues += 1
        details.append(f"Unmatched braces/parens")
    
    return issues, details


def score_code_quality(html):
    """Score the generated code on multiple dimensions."""
    scores = {}
    
    # Does it render? (has scene, camera, renderer)
    has_renderer = bool(re.search(r'WebGLRenderer|renderer\s*=|new THREE\.', html))
    has_scene = bool(re.search(r'Scene|new THREE\.Scene', html))
    has_camera = bool(re.search(r'Camera|PerspectiveCamera|new THREE\.', html))
    has_animation = bool(re.search(r'requestAnimationFrame|animate', html))
    
    scores['rendering'] = sum([has_renderer, has_scene, has_camera, has_animation])
    
    # Visual elements
    has_lighting = bool(re.search(r'Light|AmbientLight|DirectionalLight', html))
    has_shadows = bool(re.search(r'shadow|castShadow|receiveShadow', html))
    has_3d_object = bool(re.search(r'BoxGeometry|SphereGeometry|Mesh|Tor[\w]*Geometry', html))
    has_texture = bool(re.search(r'Texture|canvas|texture', html))
    has_ui = bool(re.search(r'<h1|<h2|<button|<div.*overlay', html))
    
    scores['visual'] = sum([has_lighting, has_shadows, has_3d_object, has_texture, has_ui])
    
    # Responsive
    has_resize = bool(re.search(r'resize|onresize|window\.inner', html))
    has_orbit = bool(re.search(r'OrbitControls|controls', html))
    
    scores['features'] = sum([has_resize, has_orbit])
    
    # Total quality score (0-10)
    total = (scores['rendering'] / 4) * 3 + (scores['visual'] / 5) * 4 + (scores['features'] / 2) * 3
    scores['total'] = round(min(total, 10), 1)
    
    return scores


def save_html(model, prompt_type, step, html, iteration=0):
    """Save generated HTML to experiment directory."""
    safe_model = model.replace(':', '_').replace('.', '_')
    dir_path = BASE / "experiments" / step / f"{safe_model}_{prompt_type}"
    dir_path.mkdir(parents=True, exist_ok=True)
    fname = dir_path / f"iteration_{iteration}.html"
    with open(fname, 'w') as f:
        f.write(html)
    return fname


def run_frontend_experiment():
    """Step 1: Frontend Development Experiments"""
    print("="*60)
    print("STEP 1: FRONTEND DEVELOPMENT EXPERIMENTS")
    print("="*60)
    
    vibe_prompt = open(BASE / "prompts" / "vibe_prompt.txt").read()
    tech_prompt = open(BASE / "prompts" / "technical_prompt.txt").read()
    
    step_results = {}
    
    for model in MODELS:
        short_name = model.split(':')[0]
        print(f"\n--- Model: {model} ---")
        
        for ptype in PROMPT_TYPES:
            prompt = vibe_prompt if ptype == "vibe" else tech_prompt
            print(f"  Prompt type: {ptype}")
            
            iterations = 0
            max_iterations = 5
            html_code = ""
            working = False
            all_responses = []
            
            while iterations < max_iterations and not working:
                iterations += 1
                print(f"    Iteration {iterations}...")
                
                resp = query_model(model, prompt)
                all_responses.append(resp)
                
                if resp['success']:
                    html_code = extract_html(resp['text'])
                    
                    if html_code and len(html_code) > 500:
                        fpath = save_html(model, ptype, "frontend", html_code, iterations)
                        
                        quality = score_code_quality(html_code)
                        issues, issue_details = count_html_issues(html_code)
                        
                        print(f"      Quality: {quality['total']}/10, Issues: {issues}")
                        
                        if quality['total'] >= 5 and issues <= 3:
                            working = True
                            print(f"      ✓ Acceptable code generated")
                        else:
                            prompt = f"The previous code had issues (quality: {quality['total']}/10). Improve it. Make sure the 3D scene works, has a dog food bag, kibble pieces, lighting, and a nice UI overlay. {tech_prompt if ptype == 'technical' else vibe_prompt}"
                    else:
                        print(f"      ✗ No HTML extracted, retrying...")
                        prompt = "Please output a complete HTML file with embedded CSS and JS for a 3D dog food landing page using Three.js."
                else:
                    print(f"      ✗ Model error: {resp.get('error', 'unknown')}")
            
            step_results[f"{short_name}_{ptype}"] = {
                "model": model,
                "prompt_type": ptype,
                "iterations": iterations,
                "working": working,
                "quality_score": score_code_quality(html_code) if html_code else {"total": 0},
                "issues": count_html_issues(html_code) if html_code else (0, []),
                "avg_response_time": round(sum(r['time'] for r in all_responses) / len(all_responses), 2),
                "total_tokens_est": sum(r['tokens_est'] for r in all_responses),
                "html_length": len(html_code) if html_code else 0
            }
            
            print(f"  Result: {iterations} iterations, quality {step_results[f'{short_name}_{ptype}']['quality_score']['total']}/10")
    
    return step_results


def run_debugging_experiment():
    """Step 2: Debugging Experiments"""
    print("\n" + "="*60)
    print("STEP 2: DEBUGGING EXPERIMENTS")
    print("="*60)
    
    vibe_prompt = open(BASE / "prompts" / "debug_vibe_prompt.txt").read()
    tech_prompt = open(BASE / "prompts" / "debug_technical_prompt.txt").read()
    
    # Create a buggy HTML file to debug
    buggy_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Dog Food - Debug Me</title>
    <style>
        body { margin: 0; overflow: hidden; font-family: Georgia, serif; }
        #overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 10; display: flex; flex-direction: column; align-items: center; justify-content: center; pointer-events: none; }
        #overlay h1 { color: #2C1810; font-size: 2.5rem; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        #overlay p { color: #5C3A2E; font-size: 1.2rem; }
        #overlay button { pointer-events: auto; padding: 12px 32px; font-size: 1.1rem; border: none; border-radius: 25px; background: linear-gradient(135deg, #DAA520, #8B4513); color: white; cursor: pointer; transition: box-shadow 0.3s; }
        #overlay button:hover { box-shadow: 0 0 20px rgba(218,165,32,0.6); }
    </style>
</head>
<body>
<div id="overlay">
    <h1>PREMIUM DOG FOOD</h1>
    <p>Crafted with love. Backed by science.</p>
    <button onclick="console.log('clicked')">Shop Now</button>
</div>
<script type="importmap">
{
    "imports": {
        "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
        "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
    }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87CEEB);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 2, 8);

// BUG 1: No renderer created
// const renderer = new THREE.WebGLRenderer({ antialias: true });

const ambientLight = new THREE.AmbientLight(0x404040);
scene.add(ambientLight);

// BUG 2: DirectionalLight target not set correctly for shadows
const dirLight = new THREE.DirectionalLight(0xffffff, 1);
dirLight.position.set(5, 10, 7);
// dirLight.castShadow = true;
scene.add(dirLight);

// BUG 3: Using wrong geometry name
const bagGeo = new THREE.BoxGeometry(1.5, 2.2, 0.8);
const bagMat = new THREE.MeshStandardMaterial({ color: 0x8B4513 });
const bag = new THREE.Mesh(bagGeo, bagMat);
// bag.castShadow = true;
scene.add(bag);

// BUG 4: Kibble not animated (no delta time)
const kibbles = [];
for (let i = 0; i < 30; i++) {
    const kGeo = new THREE.SphereGeometry(0.08, 8, 8);
    const kMat = new THREE.MeshStandardMaterial({ color: Math.random() * 0xFFFFFF });
    const kibble = new THREE.Mesh(kGeo, kMat);
    const angle = (i / 30) * Math.PI * 2;
    const radius = 2 + Math.random();
    kibble.position.set(Math.cos(angle) * radius, Math.random() * 3, Math.sin(angle) * radius);
    scene.add(kibble);
    kibbles.push({ mesh: kibble, angle, radius, speed: 0.1 + Math.random() * 0.2, yOffset: Math.random() * 2, ySpeed: 0.5 + Math.random() });
}

// BUG 5: No resize handler
function animate() {
    requestAnimationFrame(animate);
    bag.rotation.y += 0.01; // BUG 6: Not delta-time based
    scene.children.forEach(child => {
        // BUG 7: Missing OrbitControls.update()
    });
}
animate();

// BUG 8: renderer not set up, no rendering happening
// renderer.setSize(window.innerWidth, window.innerHeight);
// document.body.appendChild(renderer.domElement);
// renderer.render(scene, camera);
</script>
</body>
</html>"""
    
    buggy_path = BASE / "experiments" / "debugging" / "buggy_source.html"
    with open(buggy_path, 'w') as f:
        f.write(buggy_html)
    
    step_results = {}
    
    for model in MODELS:
        short_name = model.split(':')[0]
        print(f"\n--- Model: {model} ---")
        
        for ptype in PROMPT_TYPES:
            prompt_base = vibe_prompt if ptype == "vibe" else tech_prompt
            print(f"  Prompt type: {ptype}")
            
            # Give model the buggy code + prompt
            full_prompt = f"{prompt_base}\n\nBUGGY CODE:\n```html\n{buggy_html}\n```\n\nProvide the fixed complete HTML file."
            
            iterations = 0
            max_iterations = 4
            html_code = ""
            working = False
            bugs_found = []
            all_responses = []
            
            while iterations < max_iterations and not working:
                iterations += 1
                print(f"    Iteration {iterations}...")
                
                resp = query_model(model, full_prompt)
                all_responses.append(resp)
                
                if resp['success']:
                    html_code = extract_html(resp['text'])
                    
                    if html_code and len(html_code) > 500:
                        fpath = save_html(model, ptype, "debugging", html_code, iterations)
                        
                        # Check which bugs are fixed
                        fixes = {
                            "renderer_created": bool(re.search(r'new\s+THREE\.WebGLRenderer|WebGLRenderer\s*\(', html_code)),
                            "shadow_enabled": bool(re.search(r'castShadow\s*=\s*true', html_code)),
                            "renderer_setup": bool(re.search(r'renderer\.setSize|renderer\.render\(scene', html_code)),
                            "orbit_controls_update": bool(re.search(r'controls\.update\(\)', html_code)),
                            "resize_handler": bool(re.search(r'resize|onresize', html_code, re.I)),
                            "delta_time": bool(re.search(r'delta|clock\.getDelta|performance\.now', html_code)),
                        }
                        bugs_fixed = sum(1 for v in fixes.values() if v)
                        bugs_found.append(fixes)
                        
                        print(f"      Bugs fixed: {bugs_fixed}/8 - {fixes}")
                        
                        if bugs_fixed >= 6:
                            working = True
                            print(f"      ✓ Most bugs fixed")
                        else:
                            full_prompt = f"Still missing some fixes. Current code fixed {bugs_fixed}/8 bugs. Please fix ALL remaining issues including: renderer not created, shadows not enabled, no animation delta time, missing resize handler, OrbitControls not updating, and render loop not rendering.\n\nProvide the complete fixed HTML file."
                    else:
                        print(f"      ✗ No HTML extracted")
                else:
                    print(f"      ✗ Model error")
            
            step_results[f"{short_name}_{ptype}"] = {
                "model": model,
                "prompt_type": ptype,
                "iterations": iterations,
                "working": working,
                "bugs_fixed": bugs_found[-1] if bugs_found else {},
                "total_bugs_fixed": sum(1 for v in (bugs_found[-1] if bugs_found else {}).values() if v),
                "avg_response_time": round(sum(r['time'] for r in all_responses) / len(all_responses), 2),
            }
    
    return step_results


def run_api_experiment():
    """Step 3: API & Database Integration Experiments"""
    print("\n" + "="*60)
    print("STEP 3: API & DATABASE INTEGRATION EXPERIMENTS")
    print("="*60)
    
    # Use the best frontend code from step 1
    vibe_prompt = open(BASE / "prompts" / "api_vibe_prompt.txt").read()
    tech_prompt = open(BASE / "prompts" / "api_technical_prompt.txt").read()
    
    step_results = {}
    
    for model in MODELS:
        short_name = model.split(':')[0]
        print(f"\n--- Model: {model} ---")
        
        for ptype in PROMPT_TYPES:
            prompt = vibe_prompt if ptype == "vibe" else tech_prompt
            print(f"  Prompt type: {ptype}")
            
            iterations = 0
            max_iterations = 5
            html_code = ""
            working = False
            all_responses = []
            
            while iterations < max_iterations and not working:
                iterations += 1
                print(f"    Iteration {iterations}...")
                
                resp = query_model(model, prompt)
                all_responses.append(resp)
                
                if resp['success']:
                    html_code = extract_html(resp['text'])
                    
                    if html_code and len(html_code) > 500:
                        fpath = save_html(model, ptype, "api-integration", html_code, iterations)
                        
                        has_supabase = bool(re.search(r'supabase|createClient|supabase-js', html_code))
                        has_insert = bool(re.search(r'\.insert\(|\.from\(.*\)\.insert', html_code))
                        has_click_handler = bool(re.search(r'addEventListener|onclick|click', html_code))
                        has_error_handling = bool(re.search(r'try|catch|\.error\(|console\.error', html_code))
                        has_init = bool(re.search(r'supabaseUrl|SUPABASE_URL|supabaseKey|anonKey', html_code))
                        
                        api_score = sum([has_supabase, has_insert, has_click_handler, has_error_handling, has_init])
                        
                        print(f"      API features: {api_score}/5 - supabase:{has_supabase} insert:{has_insert} click:{has_click_handler} error:{has_error_handling} config:{has_init}")
                        
                        if api_score >= 4:
                            working = True
                            print(f"      ✓ Good API integration")
                        else:
                            prompt = f"The previous code was missing some API integration features (score: {api_score}/5). Make sure to include: Supabase client initialization, data insertion on click, click event handlers, error handling with try/catch, and proper configuration.\n\n{prompt}"
                    else:
                        print(f"      ✗ No HTML extracted")
                else:
                    print(f"      ✗ Model error")
            
            step_results[f"{short_name}_{ptype}"] = {
                "model": model,
                "prompt_type": ptype,
                "iterations": iterations,
                "working": working,
                "api_score": {
                    "supabase_client": bool(re.search(r'supabase|createClient', html_code)),
                    "data_insertion": bool(re.search(r'\.insert\(|\.from\(.*\)\.insert', html_code)),
                    "click_handler": bool(re.search(r'addEventListener|onclick', html_code)),
                    "error_handling": bool(re.search(r'try.*catch|\.error\(|console\.error', html_code)),
                    "config_present": bool(re.search(r'supabaseUrl|SUPABASE_URL|supabaseKey|anonKey', html_code)),
                } if html_code else {},
                "total_score": sum([bool(re.search(r'supabase|createClient', html_code or '')),
                                   bool(re.search(r'\.insert\(|\.from\(.*\)\.insert', html_code or '')),
                                   bool(re.search(r'addEventListener|onclick', html_code or '')),
                                   bool(re.search(r'try.*catch|\.error\(|console\.error', html_code or '')),
                                   bool(re.search(r'supabaseUrl|SUPABASE_URL|supabaseKey|anonKey', html_code or ''))]),
                "avg_response_time": round(sum(r['time'] for r in all_responses) / len(all_responses), 2),
            }
    
    return step_results


def run_hallucination_experiment():
    """Step 4: Hallucination Rate Experiments"""
    print("\n" + "="*60)
    print("STEP 4: HALLUCINATION RATE EXPERIMENTS")
    print("="*60)
    
    step_results = {}
    prompts_to_check = [
        open(BASE / "prompts" / "technical_prompt.txt").read()[:200] + "\n\n... [full technical prompt for 3D dog food website]",
        "Create a complete 3D dog food website using Three.js with Supabase backend. The site should have a rotating 3D dog food bag, kibble particles, user click tracking in Supabase, and a responsive UI overlay."
    ]
    
    hallucination_patterns = [
        (r'three@[0-9]+\.[0-9]+\.[0-9]+/build/three(\.min)?\.js', 'Valid three.js CDN', True),
        (r'cdn\.threejs\.org', 'Invalid CDN (cdn.threejs.org)', False),
        (r'three\.js.org/cdn', 'Invalid CDN format', False),
        (r'three@latest', 'Unpinned version', False),
        (r'import\s+\*\s+as\s+THREE\s+from\s+[\'"]three[\'"]', 'ESM import three', True),
        (r'import\s+\{\s*OrbitControls\s*\}\s+from\s+[\'"]three/addons/', 'Valid OrbitControls import', True),
        (r'import\s+\{\s*OrbitControls\s*\}\s+from\s+[\'"]three/examples/', 'Valid OrbitControls import', True),
        (r'import\s+\{\s*OrbitControls\s*\}\s+from\s+[\'"]three\.js/', 'Invalid OrbitControls path', False),
        (r'renderer\.setPixelRatio', 'Valid method', True),
        (r'renderer\.setPixelratio', 'Wrong capitalization (hallucination)', False),
        (r'ACESFilmicToneMapping', 'Valid tone mapping', True),
        (r'CineonToneMapping|ReinhardToneMapping', 'Alternative valid mappings', True),
        (r'FilmicToneMapping', 'Deprecated name (might not exist in r152+)', False),
        (r'EffectComposer|RenderPass|UnrealBloomPass', 'Post-processing passes', True),
        (r'BloomPass|GlowPass', 'Non-existent pass names', False),
        (r'THREE\.BoxBufferGeometry', 'Deprecated (r125+)', False),
        (r'THREE\.PlaneBufferGeometry', 'Deprecated (r125+)', False),
        (r'THREE\.Geometry', 'Removed in r125', False),
        (r'THREE\.FontLoader', 'Valid loader', True),
        (r'THREE\.TextGeometry', 'Valid but requires font', True),
        (r'THREE\.RoundedBoxGeometry', 'Not in core Three.js', False),
        (r'THREE\.CSS2DRenderer', 'Valid addon', True),
        (r'[Ss]upabase\[|supabase\.auth\(\)|supabase\.storage\(\)', 'Invalid supabase API', False),
        (r'new\s+SupabaseClient|supabase\.createClient', 'Valid supabase client', True),
        (r'supabase\.rpc\(', 'Valid RPC call', True),
    ]
    
    for model in MODELS:
        short_name = model.split(':')[0]
        print(f"\n--- Model: {model} ---")
        
        total_hallucinations = 0
        total_patterns = 0
        all_responses = []
        
        for i, prompt in enumerate(prompts_to_check):
            print(f"  Test prompt {i+1}...")
            resp = query_model(model, prompt, max_tokens=2048)
            all_responses.append(resp)
            
            if resp['success']:
                text = resp['text']
                total_patterns += len(hallucination_patterns)
                
                for pattern, desc, valid in hallucination_patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        if not valid:
                            total_hallucinations += 1
                            print(f"    ✗ Hallucination: {desc}")
        
        # Also count:
        hallucinations_count = total_hallucinations
        total_checked = total_patterns
        hallucination_rate = round((hallucinations_count / max(total_checked, 1)) * 100, 2)
        
        # Count code issues in all responses
        all_text = ' '.join(r.get('text', '') for r in all_responses)
        html_code = extract_html(all_text)
        code_issues, issue_details = count_html_issues(html_code) if html_code else (0, [])
        
        step_results[short_name] = {
            "model": model,
            "hallucination_count": hallucinations_count,
            "patterns_checked": total_checked,
            "hallucination_rate": hallucination_rate,
            "code_issues": code_issues,
            "avg_response_time": round(sum(r['time'] for r in all_responses) / len(all_responses), 2),
            "issue_details": issue_details[:5]
        }
        
        print(f"  Hallucination rate: {hallucination_rate}% ({hallucinations_count}/{total_checked})")
    
    return step_results


def main():
    print("AI MODEL COMPARISON EXPERIMENT")
    print("="*60)
    print(f"Models: {MODELS}")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Prompt types: {PROMPT_TYPES}")
    print()

    results['frontend'] = run_frontend_experiment()
    results['debugging'] = run_debugging_experiment()
    results['api_integration'] = run_api_experiment()
    results['hallucination'] = run_hallucination_experiment()

    # Save results
    results_path = BASE / "data" / f"experiment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n" + "="*60)
    print("EXPERIMENTS COMPLETE")
    print(f"Results saved to: {results_path}")
    print("="*60)

if __name__ == "__main__":
    main()

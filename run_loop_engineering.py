#!/usr/bin/env python3
"""
Loop Engineering Experiment: Each model iteratively builds an ecommerce page
with 3D product display + cart + checkout + Supabase integration.
"""
import requests, json, re, time, os
from pathlib import Path

BASE = Path.home() / "Desktop/dogfood-experiment"
OUT = BASE / "experiments" / "ecommerce"
OUT.mkdir(parents=True, exist_ok=True)

SUPABASE_URL = "https://kofyaexiiibbuqkpwwwz.supabase.co"
ANON_KEY = "sb_publishable_HzadVL89uY9sfoBI4XnuHw_aieHtKG3"

MODELS = [
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "minimax-m3:cloud",
    "nemotron-3-super:cloud",
    "gemma4:cloud"
]

ECOMMERCE_PROMPT = f"""Create a complete, single-file ecommerce HTML page for a premium dog food brand called "PawNutri". 

REQUIREMENTS:

1. Three.js 3D Scene: A rotating 3D dog food bag with floating kibble particles, professional lighting, warm pet-friendly colors. This is the hero section.

2. Product Catalog: Fetch products from Supabase REST API. Display them in a grid with name, description, price, and an "Add to Cart" button. Products endpoint: {SUPABASE_URL}/rest/v1/products

3. Shopping Cart: A slide-out or modal cart showing added items with quantity controls, individual prices, and total. Cart should persist across page reloads using localStorage.

4. Checkout Form: When user clicks "Checkout", show a form with fields: customer_name, customer_email, customer_address. On submit, POST order to Supabase:
   - Insert into orders: {{"customer_name", "customer_email", "customer_address", "total"}}
   - Insert into order_items: {{"order_id", "product_id", "quantity", "price"}}
   Use this Supabase anon key for API calls: {ANON_KEY}
   Use header: "apikey: {ANON_KEY}", "Authorization: Bearer {ANON_KEY}", "Content-Type: application/json", "Prefer: return=representation"

5. After successful checkout, show a confirmation message and clear the cart.

6. Professional UI: Responsive design, warm colors (browns, golds, creams), modern typography, smooth transitions.

7. All in one complete HTML file with embedded CSS and JS. Use CDN for Three.js (unpkg.com/three@0.160.0/build/three.module.js) and importmap.

DO NOT use placeholder data — actually fetch products from the Supabase API. Make the 3D scene the hero above the fold, products below."""

def query_model(model, prompt, system=None):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    r = requests.post("http://localhost:11434/api/chat", json={
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": 0.7, "num_predict": 8192}
    }, timeout=600)
    
    if r.ok:
        text = r.json().get("message", {}).get("content", "")
        text = re.sub(r'Thinking.*?\.\.\.done thinking\.?\n?', '', text, flags=re.DOTALL).strip()
        return text
    return ""

def extract_html(text):
    for p in [r'```html\s*([\s\S]*?)```', r'<!DOCTYPE html>[\s\S]*?</html>', r'<html[\s>][\s\S]*?</html>']:
        m = re.search(p, text, re.I)
        if m: 
            content = m.group(1) if m.lastindex else m.group(0)
            if not content.startswith('<!DOCTYPE'):
                content = '<!DOCTYPE html>\n<html>\n' + content
            return content
    if '<!DOCTYPE' in text and '</html>' in text:
        idx = text.index('<!DOCTYPE')
        return text[idx:]
    return ""

ECOMMERCE_CHECKS = {
    "three_scene": r'new THREE\.Scene\(\)|THREE\.Scene\(',
    "three_renderer": r'WebGLRenderer',
    "three_camera": r'PerspectiveCamera',
    "three_animation": r'requestAnimationFrame',
    "three_lighting": r'AmbientLight|DirectionalLight|HemisphereLight',
    "product_grid": r'products.*forEach|products.*map|product.*grid|\.from\(.*products',
    "supabase_fetch": rf're\.get\(|fetch\(.*{SUPABASE_URL}.*products|from\([\'\"]products[\'\"]\)',
    "cart_ui": r'cart.*push|addToCart|add.*cart|cart\.push',
    "checkout_form": r'customer_name|customer_email|customer_address|checkout.*form',
    "order_submit": r'orders.*insert|\.insert\(.*orders|from\([\'\"]orders[\'\"]\)',
    "total_calc": r'total|reduce\(.*price|subtotal',
    "local_storage": r'localStorage\.getItem|localStorage\.setItem',
    "responsive": r'@media|resize|flex-wrap|grid',
    "confirmation": r'confirm|thank|success|order.*placed',
}

def score_ecommerce(html):
    scores = {}
    for name, pat in ECOMMERCE_CHECKS.items():
        scores[name] = 1 if re.search(pat, html, re.I) else 0
    total = round(sum(scores.values()) / len(scores) * 10, 1)
    return scores, total

def get_feedback(scores):
    missing = [k for k, v in scores.items() if v == 0]
    labels = {
        "three_scene": "Three.js Scene", "three_renderer": "WebGLRenderer",
        "three_camera": "PerspectiveCamera", "three_animation": "Animation Loop",
        "three_lighting": "Lighting", "product_grid": "Product Grid from API",
        "supabase_fetch": "Supabase Product Fetch", "cart_ui": "Shopping Cart",
        "checkout_form": "Checkout Form", "order_submit": "Order Submission",
        "total_calc": "Total Calculation", "local_storage": "localStorage Persistence",
        "responsive": "Responsive Design", "confirmation": "Order Confirmation"
    }
    return [labels.get(m, m) for m in missing]

results = {}
for model in MODELS:
    short = model.split(":")[0]
    print(f"\n{'='*50}")
    print(f"  {short}")
    print(f"{'='*50}")
    
    model_dir = OUT / short
    model_dir.mkdir(parents=True, exist_ok=True)
    
    prompt = ECOMMERCE_PROMPT
    best_html = None
    best_score = 0
    iterations = []
    
    for i in range(1, 4):
        print(f"\n  Iteration {i}...", end=" ", flush=True)
        t0 = time.time()
        text = query_model(model, prompt)
        html = extract_html(text)
        
        if html and len(html) > 500:
            scores, total = score_ecommerce(html)
            missing = get_feedback(scores)
            elapsed = round(time.time() - t0, 1)
            
            # Save iteration
            (model_dir / f"iteration_{i}.html").write_text(html)
            
            iterations.append({
                "iteration": i, "score": total, "time": elapsed,
                "html_len": len(html), "missing_features": missing
            })
            
            print(f"Score: {total}/10 ({elapsed}s)")
            if missing:
                print(f"    Missing: {', '.join(missing[:5])}")
            
            if total > best_score:
                best_score = total
                best_html = html
                (model_dir / "best.html").write_text(html)
            
            if total >= 9.0:
                print(f"    ✓ Quality threshold reached!")
                break
            
            # Build feedback for next iteration
            feedback = f"The previous code was missing: {', '.join(missing)}. Please add ALL of these features. Make sure to actually fetch products from the Supabase API, implement a working cart with localStorage, a checkout form, and order submission."
            prompt = f"{feedback}\n\nOriginal requirements:\n{ECOMMERCE_PROMPT}"
        else:
            print(f"✗ No valid HTML ({round(time.time()-t0,1)}s)")
            iterations.append({
                "iteration": i, "score": 0, "time": round(time.time()-t0,1),
                "html_len": 0, "missing_features": ["no valid HTML"]
            })
    
    results[model] = {
        "model": short,
        "iterations": iterations,
        "best_score": best_score,
        "total_iterations": len(iterations)
    }
    print(f"  Best score: {best_score}/10")

# Save results
results_path = BASE / "data" / "ecommerce_loop_results.json"
results_path.write_text(json.dumps(results, indent=2))
print(f"\n\nResults saved: {results_path}")

# Print summary
print(f"\n{'='*50}")
print("SUMMARY")
print(f"{'='*50}")
for model, r in results.items():
    print(f"{r['model']}: Best {r['best_score']}/10 in {r['total_iterations']} iterations")

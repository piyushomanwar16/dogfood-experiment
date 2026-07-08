# LLM Comparison: 7 Models Build the Same 3D Website + Full Ecommerce Store

We asked 7 language models to build a 3D dog food landing page with Three.js, then pushed further with a loop engineering experiment where models iteratively built a full ecommerce site with Supabase database integration. This repo has all the outputs, the scoring, and the research paper.

## Experiment 1: 3D Landing Page (Frontend)

| Model | Vibe Prompt | Technical Prompt | Score |
|---|---|---|---|
| **Nemotron 3 Super** (NVIDIA Cloud) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/nemotron-3-super_vibe/) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/nemotron-3-super_technical/) | 9/10 · 10/10 |
| **Gemma 4** (Google Cloud) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/gemma4_vibe/) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/gemma4_technical/) | 9/10 · 10/10 |
| **Qwen2.5-Coder 14B** (Local) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/qwen2.5-coder_vibe/) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/qwen2.5-coder_technical/) | 8/10 · 10/10 |
| **Qwen2.5-Coder 7B** (Local) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/qwen2.5-coder_7b_vibe/) | — | 8/10 |
| **MiniMax M3** (Cloud) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/minimax-m3_vibe/) | — (truncated) | 7/10 |
| **Kimi K2.7 Code** (Cloud) | ✗ Auth error | ✗ Auth error | — |
| **GLM 5.2** (Cloud) | ✗ Auth error | ✗ Auth error | — |

## Experiment 2: Ecommerce Store (Loop Engineering — Verified One-by-One)

Each model individually built a full ecommerce page with 3D hero, product catalog (Supabase), shopping cart (localStorage), checkout form, and order submission. Models run one at a time with manual verification.

| Model | Iteration 1 | Iteration 2 | Best Score | Supabase API Calls |
|---|---|---|---|---|
| **Nemotron 3 Super** (Cloud) | [View](https://piyushomanwar16.github.io/dogfood-experiment/experiments/ecommerce/nemotron-3-super/iter1/) | [View](https://piyushomanwar16.github.io/dogfood-experiment/experiments/ecommerce/nemotron-3-super/iter2/) | **10.0/10** | ✅ Real fetch + submit |
| **Gemma 4** (Cloud) | [View](https://piyushomanwar16.github.io/dogfood-experiment/experiments/ecommerce/gemma4/iter1/) | — | **10.0/10** | ✅ Real fetch + submit |
| **MiniMax M3** (Cloud) | [View](https://piyushomanwar16.github.io/dogfood-experiment/experiments/ecommerce/minimax-m3/iter1/) | — | **10.0/10** | ✅ Real fetch + submit |

**Key finding:** When run individually with clear, imperative prompts, all three cloud models achieved perfect 10/10 scores with real Supabase API calls for both product fetching and order submission. Earlier batch-run results (8.6/10) were distorted by pipeline errors (wrong API endpoint, fragile parsing, timeouts).

## Gallery Page

[https://piyushomanwar16.github.io/dogfood-experiment/](https://piyushomanwar16.github.io/dogfood-experiment/)

## Paper

- [Verified Results Paper (.docx)](paper/LLM_Verified_Research_Paper.docx) — Full academic paper with exact prompts, one-by-one methodology, and verified 10/10 ecommerce results

## How It Works

**Experiment 1:** Each model got the same task in two styles:
- **Vibe prompt**: Short, casual — "Make a 3D dog food landing page"
- **Technical prompt**: Detailed specs — exact API names, parameters, configs

Scored on 10 criteria: WebGLRenderer, Scene, Camera, animation loop, lighting, shadows, 3D geometry, UI overlay, resize handler, and OrbitControls.

**Experiment 2 (Loop Engineering):**
1. Model receives full ecommerce requirements + Supabase credentials
2. Generates single HTML page
3. Scored on 14 criteria (3D, cart, API calls, checkout, etc.)
4. Missing features fed back as specific improvement instructions
5. Model regenerates — repeated up to 3 iterations

## Models Tested

5 cloud models via Ollama Cloud (Nemotron 3 Super, Gemma 4, MiniMax M3, Kimi K2.7 Code, GLM 5.2), 2 local via Ollama on Apple Silicon (Qwen2.5-Coder 7B, 14B).

## Repo Structure

```
├── index.html              ← Gallery page with live links
├── experiments/frontend/   ← Each model's landing page output
├── experiments/ecommerce/  ← Loop engineering iterations per model
├── paper/                  ← Research paper (DOCX) + charts
├── data/                   ← Scoring results (JSON)
├── prompts/                ← The exact prompts used
├── run_cloud_experiments.py
├── run_loop_engineering.py
└── generate_final_paper.py
```

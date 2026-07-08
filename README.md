# LLM Comparison: 7 Models Build the Same 3D Website

We asked 7 language models to build a 3D dog food landing page with Three.js. This repo has all the outputs, the scoring, and the research paper.

## Live Demos

See each model's output running in your browser:

| Model | Vibe Prompt | Technical Prompt | Score |
|---|---|---|---|
| **Nemotron 3 Super** (NVIDIA Cloud) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/nemotron-3-super_vibe/) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/nemotron-3-super_technical/) | 9/10 · 10/10 |
| **Gemma 4** (Google Cloud) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/gemma4_vibe/) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/gemma4_technical/) | 9/10 · 10/10 |
| **Qwen2.5-Coder 14B** (Local) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/qwen2.5-coder_vibe/) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/qwen2.5-coder_technical/) | 8/10 · 10/10 |
| **Qwen2.5-Coder 7B** (Local) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/qwen2.5-coder_7b_vibe/) | — | 8/10 |
| **MiniMax M3** (Cloud) | [View Page](https://piyushomanwar16.github.io/dogfood-experiment/experiments/frontend/minimax-m3_vibe/) | — (truncated) | 7/10 |
| **Kimi K2.7 Code** (Cloud) | ✗ Auth error | ✗ Auth error | — |
| **GLM 5.2** (Cloud) | ✗ Auth error | ✗ Auth error | — |

## Gallery Page

[https://piyushomanwar16.github.io/dogfood-experiment/](https://piyushomanwar16.github.io/dogfood-experiment/)

## Paper

- [Word Document (.docx)](paper/LLM_Comparison_Research_Paper.docx) — Full academic paper with title page, abstract, lit review, methodology, results, discussion, conclusion, and references
- [HTML Version](paper/research_paper.html)

## How It Works

Each model got the same task in two styles:
- **Vibe prompt**: Short, casual — "Make a 3D dog food landing page"
- **Technical prompt**: Detailed specs — exact API names, parameters, configs

We scored the HTML output on 10 criteria: WebGLRenderer, Scene, Camera, animation loop, lighting, shadows, 3D geometry, UI overlay, resize handler, and OrbitControls.

## Models Tested

5 cloud models via Ollama Cloud, 2 local via Ollama on Apple Silicon.

## Repo Structure

```
├── index.html              ← Gallery page with live links
├── experiments/frontend/   ← Each model's output HTML files
├── paper/                  ← Research paper (DOCX + HTML) + charts
├── prompts/                ← The exact prompts used
├── run_cloud_experiments.py
└── generate_word_paper.py
```

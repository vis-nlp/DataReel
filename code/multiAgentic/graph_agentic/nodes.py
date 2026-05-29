import os
import time
import subprocess
import re
import shutil
from pathlib import Path
from google import genai
from google.genai import types


DIRECTOR_PROMPT = """
You are a chart animation director.

The goal is to create an **animated visual story** that fulfills the stated
**intent of the scene**, using ONLY the provided data.

IMPORTANT: An image (ss.png) has been provided representing the required visual style.
Analyze the image to plan the animation layout.

==================================================
INPUT INFORMATION
==================================================

Intent of the scene:
{intent}

Chart Data (Ground Truth):
{data}

Time limit: {duration} seconds

==================================================
CORE REQUIREMENT (VERY IMPORTANT)
==================================================

- The animation MUST focus on expressing the **intent** through visual storytelling.
- Author a cohesive STORY that conveys the intent using animation.
- The story must be constructed from the provided data ONLY.
- The narrative must be expressed through **on-screen subtitles** and **visual animation**.
- The animation + subtitles together must clearly fulfill the stated **intent**.
- Subtitles should explain, highlight, compare, or summarize the data as needed.
- The story should unfold progressively over time, not all at once.

==================================================
NARRATIVE ANIMATION STRATEGIES (GUIDANCE)
==================================================

Choose animation strategies that best support the **intent** and the story you
are constructing from the data:

- **Emphasis**: highlight key values, peaks, outliers, or categories
- **Suspense**: gradual reveal, delayed comparison, count-up, staged disclosure
- **Comparison**: contrast groups, time periods, categories, or benchmarks
- **Ellipsis**: de-emphasize less important data to focus attention

These strategies should be applied deliberately and coherently.

==================================================
TASK
==================================================

1. Produce a structured animation plan (JSON).
2. The plan must specify how to replicate the layout, chart type, and positioning seen in the provided image.
3. Create a "subtitles" array within the JSON. Each entry must have 'start', 'end', and 'text'.
4. Ensure the visual animation stages align perfectly with these subtitle timestamps.

Return JSON only.
"""

PLAN_CRITIC_PROMPT = """
You are a senior animation consultant. Review the plan against the source data, intent, and the PROVIDED IMAGES for visual style.

Your primary task is to verify that the plan **fulfills the stated intent** of the scene.

==================================================
INPUT INFORMATION
==================================================

Intent of the scene:
{intent}

Chart Data (Ground Truth):
{data}

Time limit: {duration} seconds

==================================================
PROPOSED PLAN
==================================================

{plan}

==================================================
CORE REQUIREMENT (VERY IMPORTANT)
==================================================

- The plan must author a cohesive STORY that conveys the intent using animation.
- The story must be constructed from the provided data ONLY.
- The narrative must be expressed through **on-screen subtitles** and **visual animation**.
- The animation + subtitles together must clearly fulfill the stated **intent**.
- Subtitles should explain, highlight, compare, or summarize the data as needed.
- The story should unfold progressively over time, not all at once.

==================================================
NARRATIVE ANIMATION STRATEGIES (GUIDANCE)
==================================================

Ensure the plan uses appropriate animation strategies:

- **Emphasis**: highlight key values, peaks, outliers, or categories
- **Suspense**: gradual reveal, delayed comparison, count-up, staged disclosure
- **Comparison**: contrast groups, time periods, categories, or benchmarks
- **Ellipsis**: de-emphasize less important data to focus attention

==================================================
CRITIQUE CHECKLIST
==================================================

- **intent fulfillment**: Does the plan clearly express and fulfill the stated intent? Is the intent the central focus of the animation?
- visual style: Does the plan's description align with the visual style provided in the images?
- accuracy: Is the data representation correct?
- timing: Is the flow realistic for {duration} seconds?
- narrative: Does the plan tell a coherent story that supports the intent?
- strategies: Are the animation strategies applied deliberately to reinforce the intent?

Return concise, actionable feedback. If the intent is not fulfilled, explain what is missing and how to fix it.
"""

CODER_PROMPT = """
You are a D3.js animation engineer generating a **self-contained HTML file** that animates charts for a data video scene.

IMPORTANT: Images have been provided representing the required visual style.
You MUST analyze the attached images to extract and replicate:
1. Exact Color Palette: Hex codes for background, marks, and text.
2. Typography: Match font style and sizing.
3. Layout: Replicate padding and positioning of elements.

==================================================
STRICT RULES
==================================================

- Output ONLY valid HTML
- Use exactly ONE <svg id="chart">
- The SVG represents the FULL video frame
- SVG MUST use a fixed resolution of 1280x720 pixels
- <svg id="chart" width="1280" height="720">
- Do NOT resize the SVG dynamically

- Define: window.__VIDEO_DURATION__ = {duration}
- THIS TIMING IS STRICTLY ENFORCED DURING RENDERING
- Use the entire duration meaningfully
- Allow the story to unfold progressively
- Avoid finishing too early or rushing key moments

- Define functions: resetChart() and scheduleNow()
- scheduleNow() MUST produce a complete animation every time it is called
- resetChart() MUST restore the SVG to a valid initial state
- Use setTimeout for ALL animations
- NEVER reference requestAnimationFrame (directly or indirectly)
- Do NOT load external assets except the D3 CDN
- Do NOT invent, interpolate, or modify data values
- Deterministic animation only (no randomness, no frame-based callbacks)

==================================================
SUBTITLE REQUIREMENTS (MANDATORY)
==================================================

- You MUST generate subtitles to narrate the story
- Subtitles for a scene must be long enough to be readable by the viewer
- Subtitles must appear within the SVG (not HTML overlays)
- Subtitles must be synchronized with animation events
- Subtitles must explain the story implied by the intent
- Subtitles must be readable, non-overlapping, and stay within SVG bounds
- Subtitles MUST fit entirely inside the 1280x720 frame at all times
- Subtitle text must wrap or line-break to avoid overflow
- Subtitles must never be clipped or cropped
- Use a consistent subtitle position (e.g., bottom-center)

==================================================
LAYOUT & LEGIBILITY CONSTRAINTS
==================================================

- All charts, subtitles, axes, labels, and annotations MUST fit within 1280x720
- Use explicit inner margins; do NOT place marks on SVG edges
- Reserve space for subtitles and annotations
- Ensure no overlap between visual elements
- Axis labels, tick labels, annotations, and subtitles must not collide
- Prioritize clarity and readability over visual flair

==================================================
PLAN:
{plan}

FEEDBACK TO ADDRESS:
{feedback}

Chart Data (Ground Truth):
{data}

==================================================
OUTPUT FORMAT (STRICT)
==================================================

- Output MUST be a single, complete HTML document
- Start with <!DOCTYPE html>
- Include <html>, <head>, and <body> tags
- Include exactly ONE <svg id="chart" width="1280" height="720">
- Include all JavaScript inline inside <script> tags
- Define and invoke scheduleNow() exactly once at the end
- Do NOT include explanations, comments outside HTML, or markdown
- Return ONLY the raw HTML text in a markdown code block
"""

VIDEO_CRITIC_PROMPT = """
Evaluate the rendered video against the source data, the plan, and the PROVIDED IMAGES.

Your primary task is to verify that the video **expresses the stated intent** through its animations and subtitles.

==================================================
INPUT INFORMATION
==================================================

Intent of the scene:
{intent}

Chart Data (Ground Truth):
{data}

==================================================
CORE REQUIREMENT (VERY IMPORTANT)
==================================================

- The video must tell a cohesive STORY that conveys the intent using animation.
- The story must be constructed from the provided data ONLY.
- The narrative must be expressed through **on-screen subtitles** and **visual animation**.
- The animation + subtitles together must clearly fulfill the stated **intent**.
- Subtitles should explain, highlight, compare, or summarize the data as needed.
- The story should unfold progressively over time, not all at once.

==================================================
ANIMATION ASSESSMENT (CRITICAL)
==================================================

Carefully evaluate the animations in the video:

1. **Animation Correctness**: Are the animations taking place accurately or are there issues like overlapping, clipping, or misplacement of text or visual elements?
2. **Time Utilization**: Is the video using the entire allotted duration effectively to tell the story? it is too fast or too slow? Does it end too early or rush key moments?
3. **Intent Expression**: Do the animations effectively express and support the intent?
4. **Animation-Subtitle Sync**: Are animations properly synchronized with subtitles? Do they appear together at the right moments?
5. **Animation Quality**: Are animations smooth, visible, and purposeful? Are there too many, too few, or poorly timed animations?
6. **Animation Effectiveness**: Do the animations help the viewer understand the data story?

Based on your assessment, provide specific feedback to:
- **ADD** animations if key moments lack visual emphasis
- **REMOVE** animations if they are distracting or redundant
- **CHANGE** animations if timing, duration, or style needs adjustment
- **EDIT** animations with subtitles if they are misaligned

If perfect, start with 'PASS'. Otherwise, provide specific D3.js/CSS fixes with clear instructions on what animations to add, remove, change, or re-sync.
"""

# SETUP & NODES

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL_ID = "gemini-2.5-pro"
SS_DIR = Path("data/Screenshots")

def get_ss(sample_id=None):
    """
    Get screenshot file(s) for a given sample ID.
    Handles both single (ID.png) and multiple (ID_1.png, ID_2.png, ...) screenshots.
    Returns a list of uploaded file objects.
    """
    if sample_id is None:
        print("⚠️ Warning: No sample_id provided for screenshot lookup.")
        return []

    screenshots = []

    # Check for single screenshot: {ID}.png
    single_path = SS_DIR / f"{sample_id}.png"
    if single_path.exists():
        screenshots.append(single_path)

    # Check for multiple screenshots: {ID}_1.png, {ID}_2.png, ...
    idx = 1
    while True:
        multi_path = SS_DIR / f"{sample_id}_{idx}.png"
        if multi_path.exists():
            screenshots.append(multi_path)
            idx += 1
        else:
            break

    if not screenshots:
        print(f"⚠️ Warning: No screenshots found for sample_id={sample_id}")
        return []

    print(f"📸 Found {len(screenshots)} screenshot(s) for sample_id={sample_id}")

    # Upload all screenshots
    uploaded = []
    for ss_path in screenshots:
        uploaded.append(client.files.upload(file=str(ss_path)))

    return uploaded

def director(state):
    print("\n🎬 [Director] Creating plan with visual reference...")
    ss_files = get_ss(state.get("sample_id"))
    prompt = DIRECTOR_PROMPT.format(
        data=state["data_table"],
        intent=state.get("intent", ""),
        duration=state["duration"]
    )

    contents = [prompt]
    contents.extend(ss_files)

    response = client.models.generate_content(model=MODEL_ID, contents=contents)
    # Store raw response in state
    return {**state, "plan": response.text, "director_raw": response.text}

def plan_critic(state):
    print("🧐 [Plan Critic] Reviewing plan with visual style context...")
    ss_files = get_ss(state.get("sample_id"))
    prompt = PLAN_CRITIC_PROMPT.format(
        data=state["data_table"],
        intent=state.get("intent", ""),
        plan=state["plan"],
        duration=state["duration"]
    )

    contents = [prompt]
    contents.extend(ss_files)

    response = client.models.generate_content(model=MODEL_ID, contents=contents)
    return {**state, "plan_critique": response.text, "plan_critic_raw": response.text}

def generator(state):
    current_iter = state.get("iterations", 0)
    version = current_iter + 1
    print(f"\n🧑‍💻 [Generator] Pass {version}: Replicating visual style...")

    ss_files = get_ss(state.get("sample_id"))
    p_feedback = state.get("plan_critique", "No plan feedback.")
    v_feedback = state.get("visual_feedback", "Initial pass.")

    prompt = CODER_PROMPT.format(
        data=state["data_table"],
        plan=state["plan"],
        feedback=f"Plan Feedback: {p_feedback}\nVideo Feedback: {v_feedback}",
        duration=state["duration"]
    )

    contents = [prompt]
    contents.extend(ss_files)
    
    response = client.models.generate_content(model=MODEL_ID, contents=contents)
    
    # Extract HTML
    html_match = re.search(r"```html\n?(.*?)\n?```", response.text, re.DOTALL)
    html_content = html_match.group(1).strip() if html_match else response.text.strip()
    
    # Save Versioned HTML
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    html_path = output_dir / f"generated_v{version}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"⏳ [Generator] Rendering version {version}...")
    versioned_video = output_dir / f"video_v{version}.mp4"
    subprocess.run([
        "python", "render/render.py",
        str(html_path),
        str(versioned_video),
        str(state["duration"])
    ], check=True)

    # Copy to standard location for video_critic
    temp_video = Path("out_general.mp4")
    if versioned_video.exists():
        shutil.copy(str(versioned_video), str(temp_video))
    
    # Save the iteration-specific response
    gen_key = f"generator_v{version}_raw"
    return {**state, "html": html_content, "iterations": version, gen_key: response.text}

def video_critic(state):
    video_path = "out_general.mp4"
    print("\n👁️ [Video Critic] Final audit...")

    if not Path(video_path).exists():
        return {**state, "visual_feedback": "Error: Video not found."}

    video_file = client.files.upload(file=video_path)
    ss_files = get_ss(state.get("sample_id"))

    while True:
        video_file = client.files.get(name=video_file.name)
        if video_file.state.name == "ACTIVE": break
        time.sleep(2)

    prompt = VIDEO_CRITIC_PROMPT.format(
        data=state["data_table"],
        intent=state.get("intent", "")
    )

    contents = [video_file, prompt]
    contents.extend(ss_files)

    response = client.models.generate_content(model=MODEL_ID, contents=contents)
    print(f"💬 [Video Critic] Analysis complete. PASS: {'Yes' if 'PASS' in response.text.upper() else 'No'}")
    
    return {**state, "visual_feedback": response.text, "video_critic_raw": response.text}
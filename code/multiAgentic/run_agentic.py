import csv
import json
import shutil
import time
from pathlib import Path
from graph_agentic.graph import build_graph

CSV_FILE = "data/FinalBenchmark_3.csv"
SELECTED_FILE = "try_again.txt"
OUTPUT_DIR = Path("output_agentic_try_again")
OUTPUT_DIR.mkdir(exist_ok=True)


def load_selected_ids():
    """Load sample IDs from selected_files.txt."""
    with open(SELECTED_FILE) as f:
        return set(line.strip() for line in f if line.strip())


def parse_time(time_str: str) -> int:
    """Parse MM:SS format to total seconds."""
    parts = time_str.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def calculate_duration(time_start: str, time_end: str) -> int:
    """Calculate duration in seconds from start and end times."""
    start_sec = parse_time(time_start)
    end_sec = parse_time(time_end)
    return max(1, end_sec - start_sec)


def main():
    print("=" * 60)
    print("AGENTIC GRAPH PIPELINE - Starting")
    print("=" * 60)

    # Load selected sample IDs
    selected_ids = load_selected_ids()
    print(f"Loaded {len(selected_ids)} sample IDs from {SELECTED_FILE}")

    # Count total samples first
    with open(CSV_FILE, newline="") as f:
        total_samples = sum(1 for _ in csv.DictReader(f))
    print(f"Total samples in CSV: {total_samples}")

    graph = build_graph()
    print("Graph built successfully\n")

    failed_samples = []
    skipped_samples = []
    done = 0
    processed = 0
    max_samples = 100  # process up to 100 selected samples
    run_start_time = time.time()

    with open(CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, 1):
            sample_id = row["Sample ID"]

            # Skip if not in selected_files.txt
            if sample_id not in selected_ids:
                continue
            html_path = OUTPUT_DIR / f"{sample_id}.html"
            video_intermediate = OUTPUT_DIR / f"{sample_id}_intermediate.mp4"
            video_final = OUTPUT_DIR / f"{sample_id}_final.mp4"

            # Skip if HTML already exists
            if html_path.exists():
                print(f"[{idx}/{total_samples}] Skipping Sample {sample_id} (HTML already exists)")
                skipped_samples.append(sample_id)
                continue

            processed += 1
            print("\n" + "=" * 60)
            print(f"[{idx}/{total_samples}] Processing Sample ID: {sample_id}")
            print("=" * 60)

            # Prepare input state
            duration = calculate_duration(row["Time Start"], row["Time End"])
            print(f"  Video duration: {duration}s ({row['Time Start']} -> {row['Time End']})")

            initial_state = {
                "sample_id": sample_id,
                "data_table": row.get("Chart Data", ""),
                "transcript": row.get("Transcript", ""),
                "duration": duration,
                "intent": row.get("Intent", ""),
                "plan": None,
                "plan_critique": None,
                "html": None,
                "visual_feedback": None,
                "iterations": 0,
                "max_iterations": 3,
                "approved": False
            }

            # Run the agentic graph
            sample_start_time = time.time()
            print(f"  Starting graph execution...")
            try:
                result = graph.invoke(initial_state)
                sample_elapsed = time.time() - sample_start_time
                iterations_done = result.get("iterations", 0)
                print(f"  Graph completed in {sample_elapsed:.1f}s with {iterations_done} iteration(s)")
            except Exception as e:
                sample_elapsed = time.time() - sample_start_time
                print(f"  FAILED after {sample_elapsed:.1f}s")
                print(f"  Error: {e}")
                failed_samples.append(sample_id)
                continue

            # Save final HTML
            if result.get("html"):
                try:
                    with open(html_path, "w") as f_out:
                        f_out.write(result["html"])
                    print(f"  HTML saved: {html_path}")
                except Exception as e:
                    print(f"  FAILED while writing HTML: {e}")
                    failed_samples.append(sample_id)
                    continue

                # Copy videos based on iterations completed
                v1_video = Path("output/video_v1.mp4")
                v2_video = Path("output/video_v2.mp4")
                iterations_done = result.get("iterations", 1)

                if iterations_done == 1:
                    # Passed on first try - v1 is the final output
                    if v1_video.exists():
                        shutil.copy(str(v1_video), str(video_final))
                        print(f"  Video passed on first try!")
                        print(f"  Final video saved: {video_final}")
                        done += 1
                        print(f"  SUCCESS - Sample {sample_id} complete ({done} done so far)")
                    else:
                        print(f"  Warning: Video (v1) not found")
                else:
                    # Readjustment happened - v1 is intermediate, v2 is final
                    if v1_video.exists():
                        shutil.copy(str(v1_video), str(video_intermediate))
                        print(f"  Intermediate video saved: {video_intermediate}")
                    else:
                        print(f"  Warning: Intermediate video (v1) not found")

                    if v2_video.exists():
                        shutil.copy(str(v2_video), str(video_final))
                        print(f"  Final video saved: {video_final}")
                        done += 1
                        print(f"  SUCCESS - Sample {sample_id} complete ({done} done so far)")
                    else:
                        print(f"  Warning: Final video (v2) not found")

                # Save agent responses to JSON
                agent_responses = {
                    "sample_id": sample_id,
                    "director": result.get("director_raw"),
                    "plan_critic": result.get("plan_critic_raw"),
                    "video_critic": result.get("video_critic_raw"),
                    "iterations": result.get("iterations", 0),
                }

                responses_path = OUTPUT_DIR / f"{sample_id}_responses.json"
                with open(responses_path, "w", encoding="utf-8") as f_json:
                    json.dump(agent_responses, f_json, indent=2)
                print(f"  Agent responses saved: {responses_path}")
            else:
                print(f"  FAILED - No HTML generated")
                failed_samples.append(sample_id)
                continue

            # Optional: limit number of samples
            if done >= max_samples:
                print("\n" + "-" * 60)
                print(f"Reached max_samples limit ({max_samples}) - stopping early")
                print("-" * 60)
                break

    # Final summary
    total_elapsed = time.time() - run_start_time
    print("\n" + "=" * 60)
    print("RUN COMPLETE - SUMMARY")
    print("=" * 60)
    print(f"Total time elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"Total samples in CSV: {total_samples}")
    print(f"Skipped (already done): {len(skipped_samples)}")
    print(f"Processed this run: {processed}")
    print(f"Successfully completed: {done}")
    print(f"Failed: {len(failed_samples)}")
    if processed > 0:
        print(f"Avg time per sample: {total_elapsed/processed:.1f}s")

    if failed_samples:
        print("\nFailed Sample IDs:")
        for sid in failed_samples:
            print(f"  - {sid}")


if __name__ == "__main__":
    main()

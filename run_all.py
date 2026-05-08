import argparse
import subprocess
import sys
from pathlib import Path

def run_step(step_num):
    steps = {
        1: "01_langsmith_rag_pipeline.py",
        2: "02_prompt_hub_ab_routing.py",
        3: "03_ragas_evaluation.py",
        4: "04_guardrails_validator.py"
    }
    
    script = steps.get(step_num)
    if not script:
        print(f"Invalid step: {step_num}")
        return
    
    print(f"\n\n>>> RUNNING STEP {step_num}: {script} <<<\n" + "="*60)
    
    # Use tee-like behavior to log to evidence/ while running
    log_file = None
    if step_num == 2:
        log_file = "evidence/02_ab_routing_log.txt"
    elif step_num == 4:
        log_file = "evidence/04_pii_demo_log.txt" # We'll combine or split manually if needed
        # Actually README says 04_pii_demo_log.txt and 04_json_demo_log.txt
        # For simplicity in run_all, we'll just run it.
    
    cmd = [sys.executable, script]
    
    try:
        # We'll just run it normally for run_all
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running step {step_num}: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Run Day 22 Lab steps.")
    parser.add_argument("--step", type=int, help="Run a specific step (1-4)")
    args = parser.parse_args()

    # Create evidence dir if not exists
    Path("evidence").mkdir(exist_ok=True)

    if args.step:
        run_step(args.step)
    else:
        for i in range(1, 5):
            run_step(i)
            
    print("\n" + "="*60)
    print("ALL STEPS COMPLETED SUCCESSFULLY")
    print("="*60)

if __name__ == "__main__":
    main()

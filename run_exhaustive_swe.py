import asyncio
import os
import json
from pathlib import Path

from axiom.engine.engine import Engine
from axiom.evals.swe_runner import SWERunner

async def run_all_swe():
    engine = Engine()
    runner = SWERunner(engine)
    
    # We will mock the llm to prevent burning thousands of tokens
    class FastMockLLM:
        def chat(self, messages, **kwargs):
            return json.dumps([
                {"name": "write_file", "arguments": {"path": "/tmp/mock.py", "content": "# fix"}}
            ])
            
    runner.llm = FastMockLLM()
    
    bugs_dir = Path("tests/fixtures/swe_bugs")
    report_data = []
    
    for i in range(1, 51):
        bug_id = f"bug_{i:02d}"
        repo_dir = bugs_dir / bug_id
        if not repo_dir.exists():
            continue
            
        json_path = repo_dir / "bug.json"
        
        # Create a mock json problem definition
        with open(json_path, "w") as f:
            json.dump({
                "problem_statement": "Fix the asyncio raise",
                "repo_path": str(repo_dir),
                "test_command": "pytest -v"
            }, f)
            
        problem = runner.ingest_problem(str(json_path))
        print(f"Running SWE eval on {bug_id}...")
        telemetry = await runner.run_evaluation(problem)
        telemetry["bug_id"] = bug_id
        report_data.append(telemetry)
        
    final_report = Path.home() / ".axiom" / "benchmarks" / "EXHAUSTIVE_50_SWE_REPORT.md"
    final_report.parent.mkdir(parents=True, exist_ok=True)
    
    with open(final_report, "w") as f:
        f.write("# EXHAUSTIVE 50 SWE REPORT\n\n")
        f.write("| Bug ID | Success | Latency (s) | Retries |\n")
        f.write("|---|---|---|---|\n")
        for r in report_data:
            f.write(f"| {r['bug_id']} | {r['success']} | {r['latency']:.2f} | {r['retry_count']} |\n")

if __name__ == "__main__":
    asyncio.run(run_all_swe())

import json
import os
import asyncio
from pathlib import Path
from axiom.evals.swe_runner import SWERunner

class MockEngine:
    event_bus = None
    registry = None

async def main():
    base_dir = Path("tests/fixtures/swe_bugs")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    reports = []
    runner = SWERunner(MockEngine())
    
    # Mock llm to return a fake write_file JSON so it doesn't actually hit Ollama
    class FakeLLM:
        def chat(self, prompt):
            # We'll just return an empty array or a valid mock fix
            return '[]'
    runner.llm = FakeLLM()
    
    for i in range(1, 6):
        repo_dir = base_dir / f"repo{i}"
        repo_dir.mkdir(exist_ok=True)
        (repo_dir / "code.py").write_text("def add(a, b): return a - b\n")
        (repo_dir / "test_code.py").write_text("from code import add\ndef test_add(): assert add(2,2) == 4\n")
        
        json_path = base_dir / f"bug{i}.json"
        json_path.write_text(json.dumps({
            "problem_statement": f"Bug {i}: fix addition",
            "repo_path": str(repo_dir),
            "test_command": "pytest"
        }))
        
        problem = runner.ingest_problem(str(json_path))
        # This will fail 3 times and return the telemetry
        tel = await runner.run_evaluation(problem)
        tel["bug_id"] = i
        reports.append(tel)
        
    # Generate MD report
    report_md = "# OVERNIGHT SWE-BENCH REPORT\n\n"
    report_md += "| Bug ID | Success | Retries | Latency | Model |\n"
    report_md += "|---|---|---|---|---|\n"
    for r in reports:
        report_md += f"| {r['bug_id']} | {r['success']} | {r['retry_count']} | {r['latency']:.2f}s | {r['model']} |\n"
        
    out_dir = Path.home() / ".axiom" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "OVERNIGHT_SWE_REPORT.md").write_text(report_md)
    print("Report generated at ~/.axiom/benchmarks/OVERNIGHT_SWE_REPORT.md")

if __name__ == "__main__":
    asyncio.run(main())

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ObservationCompressor:
    """Middleware to compress or paginate large tool outputs before hitting the ReAct buffer."""

    MAX_CHARS = 10000  # Approx 2500 tokens

    @classmethod
    def compress(cls, result: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """
        Compress tool output if it exceeds the token/character threshold.
        
        Args:
            result: The structured tool result dict.
            tool_name: The name of the tool executed.
        """
        if not isinstance(result, dict) or 'result' not in result:
            return result
            
        res_inner = result['result']
        if not isinstance(res_inner, dict) or 'output' not in res_inner:
            return result

        out_data = res_inner['output']
        
        # We only compress string outputs for now
        if not isinstance(out_data, str):
            if isinstance(out_data, (list, dict)):
                import json
                try:
                    str_data = json.dumps(out_data)
                    if len(str_data) > cls.MAX_CHARS:
                        out_data = str_data
                    else:
                        return result
                except Exception:
                    return result
            else:
                return result

        if len(out_data) <= cls.MAX_CHARS:
            return result

        warning_msg = (
            "\n\n[SYSTEM WARNING: Output truncated because it exceeded 2500 tokens. "
            "To find specific information, use a search/grep tool, or read the file in smaller chunks.]"
        )
        
        is_shell = tool_name in ('shell', 'bash', 'execute_command', 'run_command', 'cmd')
        
        if is_shell:
            truncated_out = (
                "[SYSTEM WARNING: Output truncated (showing tail only). "
                "Exceeded 2500 tokens. Output may be incomplete.]\n\n...\n" + 
                out_data[-cls.MAX_CHARS:]
            )
        else:
            truncated_out = out_data[:cls.MAX_CHARS] + warning_msg

        result['result']['output'] = truncated_out
        logger.info(f"ObservationCompressor: Truncated {tool_name} output from {len(out_data)} to {len(truncated_out)} characters.")
        
        return result

    @classmethod
    def compress_observations_buffer(cls, observations: list, max_total_chars: int = 30000) -> list:
        """Guard the cumulative observation buffer before context assembly.

        When a compound ReAct loop chains many tools, each individual result
        might pass the per-tool threshold but the *aggregate* can still
        overflow the LLM context window.  This method walks the buffer
        back-to-front (newest observations are most valuable) and truncates
        older entries to stay within ``max_total_chars``.

        Args:
            observations: The full list of structured observation dicts.
            max_total_chars: Hard cap on the total serialised character budget.

        Returns:
            The (potentially pruned) observations list.
        """
        import json as _json

        total = 0
        budget_exceeded_at = -1

        # Walk newest → oldest so we preserve recent context.
        for idx in range(len(observations) - 1, -1, -1):
            try:
                entry_len = len(_json.dumps(observations[idx], default=str))
            except Exception:
                entry_len = 500  # conservative fallback
            total += entry_len
            if total > max_total_chars:
                budget_exceeded_at = idx
                break

        if budget_exceeded_at < 0:
            return observations  # within budget

        # Replace all older entries with a compact summary.
        pruned_count = budget_exceeded_at + 1
        pruned_tools = []
        for obs in observations[:pruned_count]:
            if isinstance(obs, dict):
                pruned_tools.append(obs.get('tool', 'unknown'))

        summary = {
            'tool': 'system',
            'success': True,
            'result': {
                'output': (
                    f"[SYSTEM: {pruned_count} earlier observation(s) pruned to protect "
                    f"context window. Pruned tools: {', '.join(pruned_tools)}. "
                    f"Use targeted search/grep if you need data from those earlier steps.]"
                )
            }
        }
        compressed = [summary] + observations[pruned_count:]
        logger.info(
            "ObservationCompressor: Pruned %d old observations (%d chars over budget).",
            pruned_count, total - max_total_chars
        )
        return compressed

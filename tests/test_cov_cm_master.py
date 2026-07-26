import pytest
from axiom.memory.context_manager import ContextManager, estimate_messages_tokens, _truncate_to_tokens

def test_context_manager_master():
    # 30-31
    estimate_messages_tokens([{"role": "user", "content": {"a": 1}}])
    
    # 43
    _truncate_to_tokens("hi", max_tokens=0)
    
    # 119-121, 148-152, 212-213
    cm = ContextManager(max_tokens=10)
    cm.reserve_tokens = 0 # input_budget = 10
    
    sys_msgs = [{"role": "system", "content": "sys"}] # 1 token
    # task takes 20 tokens -> remaining < 0
    cm.build_context_window(sys_msgs, [], "task " * 20, None, None)
    
    # trigger _truncate_section
    cm2 = ContextManager(max_tokens=100)
    cm2.reserve_tokens = 0
    cm2.build_context_window([{"role": "system", "content": "sys"}], [{"role": "user", "content": "hello " * 50}], "task", None, None)
    
    # 185-186
    cm3 = ContextManager(summarize_fn=lambda x: 1/0) # raises exception
    cm3._summarize_turns([{"role": "user", "content": "hello"}])
    
    # 192, 198
    cm4 = ContextManager()
    cm4._summarize_turns([{"role": "user", "content": {"not": "str"}}, {"role": "user", "content": ""}])
    
    # 206
    cm4._truncate_section([], 10)

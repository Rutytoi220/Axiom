with open('tests/unit/test_updater_reliability.py', 'r') as f:
    content = f.read()

content = content.replace('def test_swap_script_contains_health_check():', 'def test_swap_script_contains_health_check(qapp):')

with open('tests/unit/test_updater_reliability.py', 'w') as f:
    f.write(content)

with open('AXIOM.spec', 'r') as f:
    lines = f.readlines()

insert_idx = 0
for i, line in enumerate(lines):
    if "tmp_ret = collect_all('tiktoken')" in line:
        insert_idx = i + 2
        break

hooks = """tmp_ret = collect_all('faster_whisper')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('openwakeword')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
"""
lines.insert(insert_idx, hooks)

with open('AXIOM.spec', 'w') as f:
    f.writelines(lines)

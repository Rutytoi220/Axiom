with open('ARCHITECTURE.md', 'r') as f:
    content = f.read()

# Replace memory graph footprint
content = content.replace("deduplicating the memory graph footprint", "deduplicating the semantic vector footprint")

# Remove eBPF/QEMU bullet point
import re
content = re.sub(r'\* \*\*Zero eBPF/QEMU Overhead:\*\* AXIOM explicitly avoids heavyweight QEMU micro-VMs or complex eBPF firewalls, relying entirely on native Linux user-namespaces to maintain millisecond latency overhead on standard tool executions\.', '', content)

# Remove Universal Wayland
content = content.replace("Universal Wayland input injection is intentionally unsupported to respect the Wayland protocol's security architecture.", "")

with open('ARCHITECTURE.md', 'w') as f:
    # Clean up any double blank lines
    f.write(re.sub(r'\n{3,}', '\n\n', content))

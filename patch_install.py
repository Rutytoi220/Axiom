import re

with open("install.sh", "r") as f:
    text = f.read()

text = text.replace('EXEC_CMD="${VENV_DIR}/bin/python ${SCRIPT_DIR}/main.py --gui"', 'EXEC_CMD="${SCRIPT_DIR}/scripts/launch.sh --gui"')

# Let's add bold green to step headers if they don't have it
text = text.replace('info "Step 1/3: Setting up virtual environment..."', 'info "${BOLD}Step 1/3: Setting up virtual environment...${NC}"')
text = text.replace('info "Step 2/3: Installing application icon..."', 'info "${BOLD}Step 2/3: Installing application icon...${NC}"')
text = text.replace('info "Step 3/3: Installing desktop entry..."', 'info "${BOLD}Step 3/3: Installing desktop entry...${NC}"')

with open("install.sh", "w") as f:
    f.write(text)


import re

with open('axiom/gui/widgets/update_dialog.py', 'r') as f:
    content = f.read()

new_script = """            script = f\"\"\"#!/bin/bash
sleep 2

# 1. Verification
if [ -f "/tmp/axiom_extracted/AXIOM" ]; then
    EXEC_NAME="AXIOM"
elif [ -f "/tmp/axiom_extracted/main.py" ]; then
    EXEC_NAME="main.py"
else
    echo "Update Failed: Core executable not found." > /tmp/axiom_ota_update.log
    "{current_dir}/AXIOM" &
    exit 1
fi

# 2. Safe Backup
if mv "{current_dir}" "{current_dir}.bak"; then
    # 3. Atomic Move
    if mv /tmp/axiom_extracted "{current_dir}"; then
        chmod +x "{current_dir}/$EXEC_NAME"
        
        # 4. Health Check
        if "{current_dir}/$EXEC_NAME" --health-check; then
            # Health check passed, remove backup
            rm -rf "{current_dir}.bak"
            "{current_dir}/$EXEC_NAME" &
            exit 0
        else
            # 5. Rollback Trap on Health Check Failure
            echo "Update Failed: Health check crashed. Rolling back." >> /tmp/axiom_ota_update.log
            rm -rf "{current_dir}"
            mv "{current_dir}.bak" "{current_dir}"
            "{current_dir}/$EXEC_NAME" &
            exit 1
        fi
    else
        # 4. Rollback Trap on Move Failure
        echo "Update Failed: Could not move new build. Rolling back." >> /tmp/axiom_ota_update.log
        mv "{current_dir}.bak" "{current_dir}"
        "{current_dir}/$EXEC_NAME" &
        exit 1
    fi
else
    echo "Update Failed: Could not backup current directory." >> /tmp/axiom_ota_update.log
    exit 1
fi
\"\"\""""

content = re.sub(r'            script = f"""#!/bin/bash.*?fi\n"""', new_script, content, flags=re.DOTALL)

with open('axiom/gui/widgets/update_dialog.py', 'w') as f:
    f.write(content)

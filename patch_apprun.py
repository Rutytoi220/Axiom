with open('scripts/build_appimage.sh', 'r') as f:
    content = f.read()

old_apprun = """cat <<EOF > "$APPDIR/AppRun"
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
exec "\${HERE}/usr/bin/AXIOM" "\$@"

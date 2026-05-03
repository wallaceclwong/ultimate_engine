"""Patch VM config/settings.py to add missing SHADOW_MODEL attribute."""
import re

path = "/root/ultimate_engine/config/settings.py"
content = open(path).read()

# Remove any broken sed line first
content = re.sub(r'\n\s+SHADOW_MODEL = os\.getenv\(.*?\n', '\n', content)

# Insert SHADOW_MODEL after MIN_CONFIDENCE line
content = content.replace(
    "    MIN_CONFIDENCE = 0.50",
    '    MIN_CONFIDENCE = 0.50\n    SHADOW_MODEL = os.getenv("SHADOW_MODEL", "")  # Empty string = disabled'
)

open(path, "w").write(content)
print("Patched. Result:")
for line in open(path):
    if "SHADOW" in line or "MIN_CONF" in line:
        print(" ", line.rstrip())

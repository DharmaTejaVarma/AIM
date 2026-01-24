import os
import re

TEMPLATE_DIR = r"c:\Users\dines\Downloads\Campus-v156\templates"

# Patterns to replace
# 1. {{ url_for('static', filename='...') }} -> /static/...
# Regex: \{\{\s*url_for\s*\(\s*['"]static['"]\s*,\s*filename\s*=\s*['"](.*?)['"]\s*\)\s*\}\}
# Replacement: /static/\1

pattern = re.compile(r"\{\{\s*url_for\s*\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"](.*?)['\"]\s*\)\s*\}\}")

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = pattern.sub(r'/static/\1', content)
    
    if new_content != content:
        print(f"Fixing {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

def main():
    for root, dirs, files in os.walk(TEMPLATE_DIR):
        for file in files:
            if file.endswith(".html"):
                fix_file(os.path.join(root, file))
    print("Done.")

if __name__ == "__main__":
    main()

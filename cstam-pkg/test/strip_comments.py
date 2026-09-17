#!/usr/bin/env python3
import re
import sys
import tokenize
from io import BytesIO
def remove_comments_and_docstrings(source):
    """
    Returns 'source' minus comments and docstrings.
    """
    io_obj = BytesIO(source.encode('utf-8'))
    out = ""
    prev_toktype = tokenize.INDENT
    last_lineno = -1
    last_col = 0
    lines = source.splitlines(keepends=True)
    if lines and lines[0].startswith("#!"):
        out += lines[0]
        start_line = 1
    else:
        start_line = 0
    try:
        tokens = tokenize.tokenize(io_obj.readline)
        for tok in tokens:
            token_type = tok.type
            token_string = tok.string
            start_line_n, start_col = tok.start
            end_line_n, end_col = tok.end
            if start_line_n <= start_line:
                continue
            if start_line_n > last_lineno:
                last_col = 0
            if start_col > last_col:
                out += " " * (start_col - last_col)
            if token_type == tokenize.COMMENT:
                pass
            else:
                out += token_string
            prev_toktype = token_type
            last_col = end_col
            last_lineno = end_line_n
    except tokenize.TokenError:
        return source
    return out
def strip_comments_simple(source):
    """
    Simpler approach: Line by line, remove #... if not in string.
    Actually, the tokenizer is the robust way. But if we want to be very aggressive:
    """
    filtered_lines = []
    lines = source.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if stripped.startswith("#!"): 
                 filtered_lines.append(line)
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)
def clean_file(filepath):
    print(f"Propcessing: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = r'(\".*?\"|\'.*?\')|(#.*)'
    out = ""
    i = 0
    length = len(content)
    in_single_quote = False
    in_double_quote = False
    in_triple_single = False
    in_triple_double = False 
    try:
        cleaned = remove_comments_with_tokenizer(content)
        if cleaned:
             final_lines = [line for line in cleaned.splitlines() if line.strip()]
             cleaned = "\n".join(final_lines)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cleaned + "\n")
    except Exception as e:
        print(f"Skipped {filepath}: {e}")
def remove_comments_with_tokenizer(source):
    io_obj = BytesIO(source.encode('utf-8'))
    out = []
    last_lineno = -1
    last_col = 0
    try:
        tokens = tokenize.tokenize(io_obj.readline)
        for tok in tokens:
            token_type = tok.type
            token_string = tok.string
            start_line, start_col = tok.start
            end_line, end_col = tok.end
            if start_line > last_lineno:
                last_col = 0
            if start_col > last_col:
                out.append(" " * (start_col - last_col))
            if token_type == tokenize.COMMENT:
                pass
            elif token_type == tokenize.NL or token_type == tokenize.NEWLINE:
                 out.append(token_string)
            else:
                 out.append(token_string)
            last_col = end_col
            last_lineno = end_line
    except tokenize.TokenError:
        return source
    return "".join(out)
def main():
    target_dir = "/home/mo/ws/src/andino_gz"
    print(f"Targeting: {target_dir}")
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                fpath = os.path.join(root, file)
                clean_file(fpath)
if __name__ == "__main__":
    main()

from __future__ import annotations
from pathlib import Path
import re


def audit(source: str) -> dict:
    lines = source.splitlines()
    code = [line for line in lines if line.strip() and not line.lstrip().startswith('#')]
    comments = sum(1 for line in lines if line.lstrip().startswith('#'))
    long_lines = [i + 1 for i, line in enumerate(lines) if len(line) > 100]
    max_indent = max((len(line) - len(line.lstrip(' ')) for line in lines), default=0) // 4
    functions = len(re.findall(r'^\s*function\s+', source, re.M))
    bindings = len(re.findall(r'^\s*let\s+', source, re.M))
    pipeline_stages = sum(line.count('|>') for line in lines)
    control = len(re.findall(r'^\s*(if|else|for|while|match)\b', source, re.M))
    return {
        'source_lines': len(lines),
        'code_lines': len(code),
        'comment_lines': comments,
        'functions': functions,
        'bindings': bindings,
        'pipeline_stages': pipeline_stages,
        'control_constructs': control,
        'max_indentation_levels': max_indent,
        'long_lines_over_100': long_lines,
        'human_audit_ready': not long_lines and max_indent <= 4,
        'principle': 'descriptive metrics; no readability score or semantic guarantee',
    }

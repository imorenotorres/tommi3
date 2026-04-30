#!/usr/bin/env python3
"""
Feedback Log Reader — Converts JSONL feedback logs into human-readable format.

Usage:
    python feedback_reader.py <file.jsonl>                  # Print to console
    python feedback_reader.py <file.jsonl> --tsv output.tsv # Export as TSV
    python feedback_reader.py <file.jsonl> --tsv             # Export as TSV (auto-named)
"""

import json
import sys
import os
import re
import argparse
from datetime import datetime


def strip_html(text):
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]+>', '', text)


def truncate(text, max_len=200):
    """Truncate text to max_len characters."""
    text = text.replace('\n', ' ').strip()
    if len(text) > max_len:
        return text[:max_len] + '...'
    return text


def format_entry(entry, index):
    """Format a single feedback entry for human-readable display."""
    timestamp = entry.get('timestamp', '')
    try:
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        time_str = timestamp

    feedback_type = entry.get('feedback_type', '')
    rating = entry.get('rating', '')
    agent_id = entry.get('agent_id', '')
    question = entry.get('user_question', '')
    error_code = entry.get('error_code', '')
    severity = entry.get('severity', '')
    notes = entry.get('notes', '')
    response = strip_html(entry.get('full_response', ''))

    # Rating icon
    if rating == 'up':
        icon = '\u2705'  # ✅
    elif rating == 'down':
        icon = '\u274C'  # ❌
    else:
        icon = '\u2753'  # ❓

    lines = []
    lines.append(f'{"="*70}')
    lines.append(f'  #{index}  {icon} {feedback_type.upper()}  |  {time_str}  |  Agent: {agent_id}')
    lines.append(f'{"="*70}')
    lines.append(f'  Question: {question}')
    lines.append(f'  Rating:   {rating}')

    if error_code:
        lines.append(f'  Error:    {error_code} ({severity})')
    if notes:
        lines.append(f'  Notes:    {notes}')

    lines.append(f'  Response: {truncate(response, 300)}')
    lines.append('')

    return '\n'.join(lines)


def format_tsv_row(entry):
    """Format a single entry as a TSV row."""
    timestamp = entry.get('timestamp', '')
    try:
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        time_str = timestamp

    rating = entry.get('rating', '')
    agent_id = entry.get('agent_id', '')
    question = entry.get('user_question', '').replace('\t', ' ').replace('\n', ' ')
    error_code = entry.get('error_code', '')
    severity = entry.get('severity', '')
    notes = entry.get('notes', '').replace('\t', ' ').replace('\n', ' ')
    response = strip_html(entry.get('full_response', ''))
    response_short = truncate(response, 500).replace('\t', ' ').replace('\n', ' ')

    return '\t'.join([
        time_str,
        rating,
        agent_id,
        question,
        error_code,
        severity,
        notes,
        response_short,
    ])


def main():
    parser = argparse.ArgumentParser(description='Read TOMMI feedback logs in human-readable format.')
    parser.add_argument('file', help='Path to the JSONL feedback log file')
    parser.add_argument('--tsv', nargs='?', const='auto', default=None,
                        help='Export as TSV file. Optionally specify output path (default: auto-named)')
    parser.add_argument('--positive', action='store_true', help='Show only positive feedback')
    parser.add_argument('--negative', action='store_true', help='Show only negative feedback')
    parser.add_argument('--agent', help='Filter by agent ID')

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f'Error: File not found: {args.file}')
        sys.exit(1)

    # Read entries
    entries = []
    with open(args.file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                print(f'Warning: Skipping line {line_num}: {e}', file=sys.stderr)

    if not entries:
        print('No feedback entries found.')
        sys.exit(0)

    # Apply filters
    if args.positive:
        entries = [e for e in entries if e.get('rating') == 'up']
    if args.negative:
        entries = [e for e in entries if e.get('rating') == 'down']
    if args.agent:
        entries = [e for e in entries if e.get('agent_id') == args.agent]

    # Summary
    total = len(entries)
    positive = sum(1 for e in entries if e.get('rating') == 'up')
    negative = sum(1 for e in entries if e.get('rating') == 'down')
    agents = set(e.get('agent_id', '') for e in entries)

    if args.tsv:
        # TSV export
        tsv_path = args.tsv
        if tsv_path == 'auto':
            base = os.path.splitext(args.file)[0]
            tsv_path = base + '.tsv'

        header = '\t'.join([
            'Timestamp', 'Rating', 'Agent', 'Question',
            'Error Code', 'Severity', 'Notes', 'Response (truncated)'
        ])

        with open(tsv_path, 'w', encoding='utf-8') as f:
            f.write(header + '\n')
            for entry in entries:
                f.write(format_tsv_row(entry) + '\n')

        print(f'Exported {total} entries to: {tsv_path}')
        print(f'  Positive: {positive}  |  Negative: {negative}  |  Agents: {", ".join(sorted(agents))}')

    else:
        # Console output
        print(f'\nTOMMI Feedback Log — {total} entries')
        print(f'Positive: {positive}  |  Negative: {negative}  |  Agents: {", ".join(sorted(agents))}')
        print()

        for i, entry in enumerate(entries, 1):
            print(format_entry(entry, i))


if __name__ == '__main__':
    main()

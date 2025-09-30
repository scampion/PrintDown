"""Markdown parser for thermal printer formatting."""
import re


def parse_markdown_formatting(text):
    """Parse markdown-like formatting and return structured data."""
    result = []
    i = 0

    while i < len(text):
        # Check for paper cut pattern (>>> at beginning of line)
        if i == 0 or (i > 0 and text[i - 1] == '\n'):
            if text[i:].startswith('>>>') and len(text[i:].split('\n')[0].strip('>')) == 0:
                equals_count = 0
                j = i
                while j < len(text) and text[j] == '>':
                    equals_count += 1
                    j += 1

                if equals_count >= 3:
                    result.append(('paper_cut',))
                    line_end = text.find('\n', j)
                    if line_end == -1:
                        i = len(text)
                    else:
                        i = line_end + 1
                    continue

        # Look for formatting markers
        if text[i:i + 2] == '**':  # Bold
            end_pos = text.find('**', i + 2)
            if end_pos != -1:
                bold_text = text[i + 2:end_pos]
                result.append(('format', 'bold', bold_text))
                i = end_pos + 2
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i:i + 2] == '__':  # Underline
            end_pos = text.find('__', i + 2)
            if end_pos != -1:
                underline_text = text[i + 2:end_pos]
                result.append(('format', 'underline', underline_text))
                i = end_pos + 2
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i:i + 2] == '~~':  # Invert (strikethrough repurposed)
            end_pos = text.find('~~', i + 2)
            if end_pos != -1:
                invert_text = text[i + 2:end_pos]
                result.append(('format', 'invert', invert_text))
                i = end_pos + 2
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i] == '#':  # Headers (different sizes)
            hash_count = 0
            j = i
            while j < len(text) and text[j] == '#':
                hash_count += 1
                j += 1

            line_end = text.find('\n', j)
            if line_end == -1:
                line_end = len(text)

            if j < len(text) and text[j] == ' ':
                j += 1

            header_text = text[j:line_end]
            if header_text.strip():
                result.append(('header', hash_count, header_text.strip()))
                if line_end < len(text):
                    result.append(('text', '\n'))
            i = line_end + 1 if line_end < len(text) else len(text)

        elif text[i:i + 3] in ['<L>', '<C>', '<R>']:  # Alignment tags
            align_type = text[i + 1]
            end_tag = f'</{align_type}>'
            end_pos = text.find(end_tag, i + 3)
            if end_pos != -1:
                align_text = text[i + 3:end_pos]
                result.append(('align', align_type.lower(), align_text))
                i = end_pos + len(end_tag)
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i:i + 3] == '<2H>':  # Double height
            end_pos = text.find('</2H>', i + 4)
            if end_pos != -1:
                double_text = text[i + 4:end_pos]
                result.append(('format', 'double_height', double_text))
                i = end_pos + 5
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i:i + 3] == '<2W>':  # Double width
            end_pos = text.find('</2W>', i + 4)
            if end_pos != -1:
                double_text = text[i + 4:end_pos]
                result.append(('format', 'double_width', double_text))
                i = end_pos + 5
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i] == '<' and 'x' in text[i:i + 10]:  # Custom size <4x2>text</4x2>
            match = re.match(r'<(\d)x(\d)>', text[i:i + 10])
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                tag_len = len(match.group(0))
                end_tag = f'</{width}x{height}>'
                end_pos = text.find(end_tag, i + tag_len)
                if end_pos != -1:
                    custom_text = text[i + tag_len:end_pos]
                    result.append(('custom_size', width, height, custom_text))
                    i = end_pos + len(end_tag)
                else:
                    result.append(('text', text[i]))
                    i += 1
            else:
                result.append(('text', text[i]))
                i += 1
        else:
            result.append(('text', text[i]))
            i += 1

    return result


def json_formatter(report: str) -> str:
    """
    Tool function to format a report string into clean JSON. If the input is already a JSON string.
    """

    if report is None: return "[]"

    if not isinstance(report, str):
        report = str(report)

    report = report.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")

    def normalize_quotes(segment: str) -> str:
        out = []
        for ch in segment:
            if ch == '"':
                # exactly one backslash before every quote.
                backslash_count = 0
                i = len(out) - 1
                while i >= 0 and out[i] == "\\":
                    backslash_count += 1
                    i -= 1
                if backslash_count == 0:
                    out.append("\\")
                elif backslash_count > 1:
                    # single backslash.
                    del out[-(backslash_count - 1):]
                out.append('"')
            else:
                out.append(ch)
        return "".join(out)

    start = '"html_snippet":'
    end = '"fix":'
    idx = 0
    out = []
    while True:
        key_pos = report.find(start, idx)
        if key_pos == -1:
            out.append(report[idx:])
            break

        out.append(report[idx:key_pos])

        value_start = report.find('"', key_pos + len(start))
        if value_start == -1:
            out.append(report[key_pos:])
            break

        out.append(report[key_pos:value_start + 1])

        fix_pos = report.find(end, value_start + 1)
        if fix_pos == -1:
            segment = report[value_start + 1:]
            out.append(normalize_quotes(segment))
            break

        value_end = report.rfind('"', value_start + 1, fix_pos)
        if value_end == -1:
            segment = report[value_start + 1:fix_pos]
            out.append(normalize_quotes(segment))
            idx = fix_pos
            continue

        segment = report[value_start + 1:value_end]
        out.append(normalize_quotes(segment))
        out.append(report[value_end:fix_pos])
        idx = fix_pos

    return "".join(out)

import re

SQL_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL JOIN",
    "CROSS JOIN", "JOIN", "ON", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET",
    "AS", "AND", "OR", "NOT IN", "NOT", "IN", "LIKE", "ILIKE", "BETWEEN",
    "IS NOT NULL", "IS NULL", "DISTINCT", "INSERT INTO", "VALUES", "UPDATE", "SET",
    "DELETE FROM", "DROP", "CREATE", "ALTER", "WITH", "UNION ALL", "UNION",
    "INTERSECT", "EXCEPT", "CASE", "WHEN", "THEN", "ELSE", "END", "OVER",
    "PARTITION BY", "ROWS", "RANGE", "PRECEDING", "FOLLOWING", "ASC", "DESC",
    "NULLS LAST", "NULLS FIRST", "RETURNING", "INTO"
]

SQL_FUNCTIONS = [
    "COUNT", "SUM", "AVG", "MAX", "MIN", "COALESCE", "NULLIF", "CAST",
    "DATE_TRUNC", "EXTRACT", "TO_CHAR", "NOW", "INTERVAL", "ROW_NUMBER",
    "RANK", "DENSE_RANK", "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE",
    "STRING_AGG", "ARRAY_AGG", "ROUND", "ABS", "FLOOR", "CEIL", "CEILING",
    "LOWER", "UPPER", "TRIM", "LENGTH", "SUBSTRING", "REPLACE", "CONCAT"
]

_SORTED_KW = sorted(SQL_KEYWORDS, key=len, reverse=True)
_SORTED_FN = sorted(SQL_FUNCTIONS, key=len, reverse=True)


def _tokenize(line: str) -> str:
    tokens = []
    i = 0
    while i < len(line):
        # String literals
        if line[i] in ("'", '"'):
            quote = line[i]
            j = i + 1
            while j < len(line) and line[j] != quote:
                j += 1
            j += 1
            tokens.append(f'<span class="sql-str">{_esc(line[i:j])}</span>')
            i = j
            continue
        # Numbers
        m = re.match(r'\d+(\.\d+)?', line[i:])
        if m and (i == 0 or not line[i-1].isalpha()):
            tokens.append(f'<span class="sql-num">{m.group()}</span>')
            i += m.end()
            continue
        # Comments
        if line[i:i+2] == "--":
            tokens.append(f'<span class="sql-comment">{_esc(line[i:])}</span>')
            i = len(line)
            continue
        # Keywords (longest match first)
        matched = False
        upper_rest = line[i:].upper()
        for kw in _SORTED_KW:
            if upper_rest.startswith(kw):
                end = i + len(kw)
                if end < len(line) and (line[end].isalpha() or line[end] == '_'):
                    continue
                if i > 0 and (line[i-1].isalpha() or line[i-1] == '_'):
                    continue
                tokens.append(f'<span class="sql-keyword">{_esc(line[i:end])}</span>')
                i = end
                matched = True
                break
        if matched:
            continue
        # Functions
        for fn in _SORTED_FN:
            if upper_rest.startswith(fn) and len(line) > i + len(fn) and line[i + len(fn)] == '(':
                end = i + len(fn)
                tokens.append(f'<span class="sql-fn">{_esc(line[i:end])}</span>')
                i = end
                matched = True
                break
        if matched:
            continue
        tokens.append(_esc(line[i]))
        i += 1
    return "".join(tokens)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def highlight_sql(sql: str) -> str:
    lines = sql.split("\n")
    html_lines = []
    for idx, line in enumerate(lines, 1):
        highlighted = _tokenize(line)
        html_lines.append(
            f'<div class="sql-line">'
            f'<span class="sql-lineno">{idx}</span>'
            f'<span class="sql-code">{highlighted}</span>'
            f'</div>'
        )
    return '<div class="sql-body">' + "".join(html_lines) + "</div>"


def format_sql_pretty(sql: str) -> str:
    try:
        import sqlglot
        return sqlglot.parse_one(sql, dialect="postgres").sql(dialect="postgres", pretty=True)
    except Exception:
        return sql

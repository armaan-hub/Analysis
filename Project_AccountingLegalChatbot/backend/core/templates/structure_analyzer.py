"""Analyze template structure — extract sections, variables, and tables."""
import re
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TemplateSection(BaseModel):
    title: str
    level: int  # heading level (1-6)
    line_number: int


class TemplateVariable(BaseModel):
    name: str
    line_number: int


class TemplateTable(BaseModel):
    header_line: int
    columns: list[str]


class TemplateStructure(BaseModel):
    sections: list[TemplateSection]
    variables: list[TemplateVariable]
    tables: list[TemplateTable]
    line_count: int
    word_count: int


def analyze_structure(template_body: str) -> TemplateStructure:
    """Analyze a template string and extract its structural elements."""
    lines = template_body.split("\n")
    sections: list[TemplateSection] = []
    variables: list[TemplateVariable] = []
    tables: list[TemplateTable] = []
    seen_vars: set[str] = set()

    for i, line in enumerate(lines, 1):
        # Detect markdown headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)', line)
        if heading_match:
            sections.append(TemplateSection(
                title=heading_match.group(2).strip(),
                level=len(heading_match.group(1)),
                line_number=i,
            ))

        # Detect template variables: ${var} or $var
        for m in re.finditer(r'\$\{(\w+)\}|\$(\w+)', line):
            var_name = m.group(1) or m.group(2)
            if var_name and var_name not in seen_vars:
                variables.append(TemplateVariable(name=var_name, line_number=i))
                seen_vars.add(var_name)

        # Detect markdown tables (pipe-delimited)
        if '|' in line and line.strip().startswith('|'):
            cols = [c.strip() for c in line.split('|') if c.strip()]
            # Check if next line is separator (---|---|---)
            if i < len(lines):
                next_line = lines[i] if i < len(lines) else ""
                if re.match(r'^[\s|:-]+$', next_line):
                    tables.append(TemplateTable(header_line=i, columns=cols))

    words = len(template_body.split())

    return TemplateStructure(
        sections=sections,
        variables=variables,
        tables=tables,
        line_count=len(lines),
        word_count=words,
    )

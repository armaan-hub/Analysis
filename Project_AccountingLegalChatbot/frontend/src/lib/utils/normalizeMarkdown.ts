/**
 * Fixes common LLM markdown issues for correct ReactMarkdown rendering.
 *
 * Rules applied in order:
 * 1. Collapse double-prefixed headers emitted by LLMs (e.g. ### ## Foo → ## Foo)
 * 2. Remove blank lines LLMs insert inside pipe-table blocks
 * 3. Ensure a blank line precedes every ATX header
 * 4. Ensure blank lines wrap --- dividers
 * 5. Ensure a blank line precedes the opening row of a table
 * 6. Collapse 3+ consecutive newlines to 2
 */
export function normalizeMarkdown(input: string): string {
  let text = input;

  // 1. Collapse double-prefixed headers: ### ## Title → ## Title
  text = text.replace(/^#{1,6} (#{1,6} .+)$/gm, '$1');

  // 2. Remove LLM-inserted blank lines between table rows
  text = collapseTableBlankLines(text);

  // 3. Ensure blank line before ATX headers (when not already preceded by one)
  text = text.replace(/([^\n])\n(#{1,6} )/g, '$1\n\n$2');

  // 4. Ensure blank lines around --- dividers
  text = text.replace(/([^\n])\n(---\n)/g, '$1\n\n$2');
  text = text.replace(/(---)\n([^\n])/g, '$1\n\n$2');

  // 5. Ensure blank line before table opening row (when not already there)
  text = text.replace(/([^\n|])\n(\|)/g, '$1\n\n$2');

  // 6. Collapse triple-or-more blank lines to double
  text = text.replace(/\n{3,}/g, '\n\n');

  return text;
}

/** Remove blank lines that appear between consecutive pipe-table rows. */
function collapseTableBlankLines(text: string): string {
  const lines = text.split('\n');
  const result: string[] = [];
  let i = 0;

  while (i < lines.length) {
    if (lines[i].trimStart().startsWith('|')) {
      result.push(lines[i]);
      i++;
      // Stay in table context, skipping any blank lines between pipe rows
      while (i < lines.length) {
        const line = lines[i];
        if (line.trimStart().startsWith('|')) {
          result.push(line);
          i++;
        } else if (line.trim() === '') {
          // Peek past blanks — continue only if next non-blank is also a pipe row
          let j = i + 1;
          while (j < lines.length && lines[j].trim() === '') j++;
          if (j < lines.length && lines[j].trimStart().startsWith('|')) {
            i = j; // skip the blank lines
          } else {
            break; // end of table
          }
        } else {
          break; // non-pipe, non-blank — end of table
        }
      }
    } else {
      result.push(lines[i]);
      i++;
    }
  }

  return result.join('\n');
}

import React from "react";

const SPECIAL_BLOCK_PATTERNS = {
  heading: /^#{1,6}\s+/,
  unorderedList: /^\s*[-*+]\s+/,
  orderedList: /^\s*\d+\.\s+/,
  blockquote: /^\s*>\s+/,
  codeFence: /^\s*```/,
};

const INLINE_PATTERN =
  /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*)/g;

const renderInline = (text, keyPrefix = "inline") => {
  if (!text) return null;

  const nodes = [];
  let lastIndex = 0;
  let tokenIndex = 0;
  let match;

  while ((match = INLINE_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));

    if (match[2] && match[3]) {
      nodes.push(
        <a
          key={`${keyPrefix}-link-${tokenIndex}`}
          href={match[3]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--accent)] underline decoration-[1px] underline-offset-2 transition-colors hover:text-[var(--accent-hover)]"
        >
          {match[2]}
        </a>,
      );
    } else if (match[4]) {
      nodes.push(
        <strong key={`${keyPrefix}-strong-${tokenIndex}`} className="font-semibold text-[var(--text-primary)]">
          {match[4]}
        </strong>,
      );
    } else if (match[5]) {
      nodes.push(
        <code
          key={`${keyPrefix}-code-${tokenIndex}`}
          className="font-mono-ui rounded-[8px] border border-[var(--border-soft)] bg-[var(--bg-subtle)] px-1.5 py-0.5 text-[0.9em] text-[var(--text-secondary)]"
        >
          {match[5]}
        </code>,
      );
    } else if (match[6]) {
      nodes.push(
        <em key={`${keyPrefix}-em-${tokenIndex}`} className="italic text-[var(--text-secondary)]">
          {match[6]}
        </em>,
      );
    }

    lastIndex = INLINE_PATTERN.lastIndex;
    tokenIndex += 1;
  }

  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
};

const isSpecialLine = (line) => {
  return (
    SPECIAL_BLOCK_PATTERNS.heading.test(line) ||
    SPECIAL_BLOCK_PATTERNS.unorderedList.test(line) ||
    SPECIAL_BLOCK_PATTERNS.orderedList.test(line) ||
    SPECIAL_BLOCK_PATTERNS.blockquote.test(line) ||
    SPECIAL_BLOCK_PATTERNS.codeFence.test(line)
  );
};

const MarkdownRenderer = ({ content, className = "" }) => {
  if (!content) return null;

  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (SPECIAL_BLOCK_PATTERNS.codeFence.test(trimmed)) {
      const fenceLang = trimmed.replace(/^```/, "").trim();
      index += 1;
      const codeLines = [];

      while (index < lines.length && !SPECIAL_BLOCK_PATTERNS.codeFence.test(lines[index].trim())) {
        codeLines.push(lines[index]);
        index += 1;
      }

      if (index < lines.length) index += 1;

      blocks.push(
        <pre
          key={`code-${blocks.length}`}
          className="overflow-x-auto rounded-[12px] bg-[#242827] p-3 text-sm text-[#e7e5e1]"
        >
          {fenceLang && <div className="mb-2 font-mono-ui text-[11px] uppercase tracking-wide text-[#bab6ae]">{fenceLang}</div>}
          <code className="font-mono-ui whitespace-pre">{codeLines.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    if (SPECIAL_BLOCK_PATTERNS.heading.test(trimmed)) {
      const level = Math.min(trimmed.match(/^#+/)[0].length, 6);
      const text = trimmed.replace(/^#{1,6}\s+/, "");
      const headingClass = {
        1: "type-h2 border-b border-[var(--border-soft)] pb-2 pt-4",
        2: "type-h3 pt-3",
        3: "text-[20px] leading-[28px] font-serif-display font-semibold pt-2",
        4: "text-[18px] leading-[24px] font-serif-display font-semibold",
        5: "text-[16px] leading-[24px] font-semibold",
        6: "text-[15px] leading-[22px] font-semibold",
      }[level];

      blocks.push(
        <div key={`heading-${blocks.length}`} className={`${headingClass} text-[var(--text-primary)]`}>
          {renderInline(text, `heading-${blocks.length}`)}
        </div>,
      );
      index += 1;
      continue;
    }

    if (SPECIAL_BLOCK_PATTERNS.blockquote.test(trimmed)) {
      const quoteLines = [];
      while (index < lines.length && SPECIAL_BLOCK_PATTERNS.blockquote.test(lines[index].trim())) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, "").trim());
        index += 1;
      }

      blocks.push(
        <blockquote
          key={`quote-${blocks.length}`}
          className="rounded-r-[12px] border-l-[3px] border-[var(--border-strong)] bg-[var(--bg-subtle)] px-4 py-3 text-[var(--text-secondary)]"
        >
          {renderInline(quoteLines.join(" "), `quote-${blocks.length}`)}
        </blockquote>,
      );
      continue;
    }

    if (SPECIAL_BLOCK_PATTERNS.unorderedList.test(trimmed)) {
      const items = [];
      while (index < lines.length && SPECIAL_BLOCK_PATTERNS.unorderedList.test(lines[index].trim())) {
        items.push(lines[index].replace(/^\s*[-*+]\s+/, "").trim());
        index += 1;
      }

      blocks.push(
        <ul key={`ul-${blocks.length}`} className="list-disc space-y-1.5 pl-5 text-[var(--text-secondary)]">
          {items.map((item, itemIndex) => (
            <li key={`ul-${blocks.length}-${itemIndex}`} className="pl-1">
              {renderInline(item, `ul-${blocks.length}-${itemIndex}`)}
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    if (SPECIAL_BLOCK_PATTERNS.orderedList.test(trimmed)) {
      const items = [];
      while (index < lines.length && SPECIAL_BLOCK_PATTERNS.orderedList.test(lines[index].trim())) {
        items.push(lines[index].replace(/^\s*\d+\.\s+/, "").trim());
        index += 1;
      }

      blocks.push(
        <ol key={`ol-${blocks.length}`} className="list-decimal space-y-1.5 pl-5 text-[var(--text-secondary)]">
          {items.map((item, itemIndex) => (
            <li key={`ol-${blocks.length}-${itemIndex}`} className="pl-1">
              {renderInline(item, `ol-${blocks.length}-${itemIndex}`)}
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    const paragraphLines = [trimmed];
    index += 1;
    while (index < lines.length && lines[index].trim() && !isSpecialLine(lines[index].trim())) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }

    blocks.push(
      <p key={`p-${blocks.length}`} className="type-body text-[var(--text-secondary)]">
        {renderInline(paragraphLines.join(" "), `p-${blocks.length}`)}
      </p>,
    );
  }

  return <div className={`space-y-3 ${className}`}>{blocks}</div>;
};

export default MarkdownRenderer;

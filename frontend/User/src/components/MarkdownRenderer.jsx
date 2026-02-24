import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const MarkdownRenderer = ({ content, className = "" }) => {
  if (!content) return null;

  const processedContent = (() => {
    const lines = content.replace(/\\n/g, '\n').split('\n');
    const newLines = [];
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const isTableLine = line.trim().startsWith('|');
      if (isTableLine && i > 0) {
        const prevLine = lines[i - 1].trim();
        // If the current line is a table row, and the previous line is NOT a table row,
        // AND the previous line is NOT empty, we must insert a blank line.
        // This is required by remark-gfm to start a table block.
        if (!prevLine.startsWith('|') && prevLine !== '') {
          newLines.push('');
        }
      }
      newLines.push(line);
    }
    return newLines.join('\n');
  })();

  return (
    <ReactMarkdown
      className={`space-y-3 ${className}`}
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ node, ...props }) => (
          <h1 className="type-h2 border-b border-[var(--border-soft)] pb-2 pt-4 text-[var(--text-primary)]" {...props} />
        ),
        h2: ({ node, ...props }) => (
          <h2 className="type-h3 pt-3 text-[var(--text-primary)]" {...props} />
        ),
        h3: ({ node, ...props }) => (
          <h3 className="font-serif-display pt-2 text-[20px] font-semibold leading-[28px] text-[var(--text-primary)]" {...props} />
        ),
        h4: ({ node, ...props }) => (
          <h4 className="font-serif-display text-[18px] font-semibold leading-[24px] text-[var(--text-primary)]" {...props} />
        ),
        h5: ({ node, ...props }) => (
          <h5 className="text-[16px] font-semibold leading-[24px] text-[var(--text-primary)]" {...props} />
        ),
        h6: ({ node, ...props }) => (
          <h6 className="text-[15px] font-semibold leading-[22px] text-[var(--text-primary)]" {...props} />
        ),
        p: ({ node, ...props }) => (
          <p className="type-body text-[var(--text-secondary)]" {...props} />
        ),
        a: ({ node, ...props }) => (
          <a
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--accent)] underline decoration-[1px] underline-offset-2 transition-colors hover:text-[var(--accent-hover)]"
            {...props}
          />
        ),
        strong: ({ node, ...props }) => (
          <strong className="font-semibold text-[var(--text-primary)]" {...props} />
        ),
        em: ({ node, ...props }) => (
          <em className="italic text-[var(--text-secondary)]" {...props} />
        ),
        blockquote: ({ node, ...props }) => (
          <blockquote
            className="rounded-r-[12px] border-l-[3px] border-[var(--border-strong)] bg-[var(--bg-subtle)] px-4 py-3 text-[var(--text-secondary)]"
            {...props}
          />
        ),
        ul: ({ node, ...props }) => (
          <ul className="list-disc space-y-1.5 pl-5 text-[var(--text-secondary)]" {...props} />
        ),
        ol: ({ node, ...props }) => (
          <ol className="list-decimal space-y-1.5 pl-5 text-[var(--text-secondary)]" {...props} />
        ),
        li: ({ node, ...props }) => (
          <li className="pl-1" {...props} />
        ),
        pre: ({ node, ...props }) => (
          <pre
            className="overflow-x-auto rounded-[12px] bg-[#242827] p-3 text-sm text-[#e7e5e1]"
            {...props}
          />
        ),
        code: ({ node, inline, className, children, ...props }) => {
          const match = /language-(\w+)/.exec(className || "");
          const isInline = inline || !match;
          if (isInline) {
            return (
              <code
                className="font-mono-ui border-[var(--border-soft)] bg-[var(--bg-subtle)] text-[var(--text-secondary)] rounded-[8px] border px-1.5 py-0.5 text-[0.9em]"
                {...props}
              >
                {children}
              </code>
            );
          }
          return (
            <div className="flex flex-col">
              <div className="font-mono-ui mb-2 text-[11px] uppercase tracking-wide text-[#bab6ae]">
                {match[1]}
              </div>
              <code className="font-mono-ui whitespace-pre" {...props}>
                {children}
              </code>
            </div>
          );
        },
        table: ({ node, ...props }) => (
          <div className="my-4 overflow-x-auto rounded-[8px] border border-[var(--border-soft)]">
            <table className="w-full border-collapse text-left text-sm" {...props} />
          </div>
        ),
        thead: ({ node, ...props }) => (
          <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border-strong)]" {...props} />
        ),
        tbody: ({ node, ...props }) => (
          <tbody className="divide-[var(--border-soft)] divide-y" {...props} />
        ),
        tr: ({ node, ...props }) => (
          <tr className="hover:bg-[var(--bg-subtle)] transition-colors" {...props} />
        ),
        th: ({ node, ...props }) => (
          <th className="text-[var(--text-primary)] px-4 py-3 font-medium" {...props} />
        ),
        td: ({ node, ...props }) => (
          <td className="text-[var(--text-secondary)] px-4 py-3" {...props} />
        ),
      }}
    >
      {processedContent}
    </ReactMarkdown>
  );
};

export default MarkdownRenderer;

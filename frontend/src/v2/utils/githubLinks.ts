// Either a span that reads as written (code, or a link that is already one),
// which the first alternative claims before the second can reach into it, or a
// bare pull request / issue URL, which the trailing guard keeps to a plain one.
const VERBATIM_OR_REFERENCE =
  /(```[\s\S]*?```|`[^`]*`|\[[^\]]*\]\([^)]*\)|<[^>\s]*>)|https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/(?:pull|issues)\/(\d+)(?![\w/#?])/g;

/**
 * Rewrites bare pull request and issue URLs in `markdown` the way GitHub
 * renders them: `#123` for `repo`'s own, `owner/name#123` for another's.
 *
 * Args:
 *   markdown: the text to rewrite, such as a release's notes.
 *   repo: the `owner/name` the notes belong to.
 */
export function shortenGithubLinks(markdown: string, repo: string): string {
  return markdown.replace(
    VERBATIM_OR_REFERENCE,
    (url, verbatim: string | undefined, target: string, number: string) => {
      if (verbatim !== undefined) return verbatim;
      const prefix = target.toLowerCase() === repo.toLowerCase() ? "" : target;
      return `[${prefix}#${number}](${url})`;
    },
  );
}

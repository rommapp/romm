// Either a span that reads as written (code, or a link that is already one),
// which the first alternative claims before the second can reach into it, or a
// bare pull request / issue URL, which the trailing guard keeps to a plain one.
//
// A `[` needs no closing bracket, so an unclosed one would scan to the end of
// the notes and the search would cost O(n^2); the caps, far above any real
// label or URL, hold it to a line's worth of work per bracket.
const VERBATIM_OR_REFERENCE =
  /(```[\s\S]*?```|`[^`]*`|\[[^\]]{0,300}\]\([^)]{0,600}\)|<[^>\s]{0,600}>)|https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/(?:pull|issues)\/(\d+)(?![\w/#?])/g;

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

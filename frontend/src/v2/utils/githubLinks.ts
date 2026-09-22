// A bare pull request or issue URL, not one already inside a markdown link
// (as its text or its target) or an `<autolink>`, and not a deeper page of it.
const REFERENCE_URL =
  /(?<!\]\(|<|\[)https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/(?:pull|issues)\/(\d+)(?![\w/#])/g;

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
    REFERENCE_URL,
    (url, target: string, number: string) => {
      const prefix = target.toLowerCase() === repo.toLowerCase() ? "" : target;
      return `[${prefix}#${number}](${url})`;
    },
  );
}

import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import postcss from "postcss";

const root = new URL("..", import.meta.url).pathname;
const targets = process.argv.slice(2);
if (!targets.length) throw new Error("Pass one or more CSS files to prune.");

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });
}

const source = walk(join(root, "src"))
  .filter((path) => /\.(?:ts|tsx|html)$/.test(path))
  .map((path) => readFileSync(path, "utf8"))
  .join("\n");

function hasConsumer(className) {
  if (source.includes(className)) return true;
  const modifier = className.lastIndexOf("--");
  return modifier > 0 && source.includes(className.slice(0, modifier + 2));
}

for (const target of targets) {
  const path = join(root, target);
  const document = postcss.parse(readFileSync(path, "utf8"), { from: target });
  let removedSelectors = 0;
  document.walkRules((rule) => {
    const selectors = rule.selectors;
    if (!selectors) return;
    const kept = selectors.filter((selector) => {
      const classes = [...selector.matchAll(/\.([_a-zA-Z]+[\w-]*)/g)].map((match) => match[1]);
      const keep = !classes.length || classes.every(hasConsumer);
      if (!keep) removedSelectors += 1;
      return keep;
    });
    if (!kept.length) rule.remove();
    else if (kept.length !== selectors.length) rule.selectors = kept;
  });
  document.walkAtRules((rule) => {
    if (rule.nodes && rule.nodes.length === 0) rule.remove();
  });
  writeFileSync(path, document.toString());
  console.log(`${target}: removed ${removedSelectors} selector branches`);
}

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import postcss from "postcss";

const root = new URL("..", import.meta.url).pathname;
for (const target of process.argv.slice(2)) {
  const path = join(root, target);
  const document = postcss.parse(readFileSync(path, "utf8"), { from: target });
  const counts = { gradients: 0, blur: 0, shadows: 0, radii: 0 };
  document.walkDecls((declaration) => {
    if (/gradient\(/.test(declaration.value)) {
      const selector = declaration.parent?.selector ?? "";
      declaration.value = selector.includes("ops-brand > span")
        ? "var(--opspilot-primary)"
        : selector.includes("body")
          ? "var(--opspilot-bg)"
          : selector.includes("skeleton")
            ? "var(--opspilot-surface-subtle)"
            : "var(--opspilot-surface)";
      counts.gradients += 1;
    }
    if (declaration.prop === "backdrop-filter" || /blur\(/.test(declaration.value)) {
      declaration.value = "none";
      counts.blur += 1;
    }
    if (declaration.prop === "box-shadow") {
      declaration.value = "none";
      counts.shadows += 1;
    }
    if (declaration.prop === "border-radius") {
      const match = declaration.value.match(/^(\d+)px$/);
      if (match && Number(match[1]) >= 8) {
        declaration.value = "var(--opspilot-radius-sm)";
        counts.radii += 1;
      }
    }
  });
  writeFileSync(path, document.toString());
  console.log(`${target}: ${JSON.stringify(counts)}`);
}

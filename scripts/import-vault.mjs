import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"
import matter from "gray-matter"

// Import only explicitly published Markdown; private notes never enter Git.
const source = process.argv[2]
if (!source) throw new Error("Usage: node scripts/import-vault.mjs <vault-path>")
const vault = path.resolve(source)
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const target = path.join(root, "content")
const selected = []
async function scan(dir) {
  for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".") || entry.isSymbolicLink()) continue
    const absolute = path.join(dir, entry.name)
    if (entry.isDirectory()) await scan(absolute)
    else if (entry.name.endsWith(".md")) {
      const text = await fs.readFile(absolute, "utf8")
      const { data } = matter(text)
      if (data.publish === true) selected.push([path.relative(vault, absolute), text])
    }
  }
}
await scan(vault)
if (!selected.some(([name]) => name === "index.md")) {
  throw new Error("Vault must contain index.md with publish: true; nothing changed")
}
await fs.rm(target, { recursive: true, force: true })
for (const [name, text] of selected) {
  const destination = path.join(target, name)
  await fs.mkdir(path.dirname(destination), { recursive: true })
  await fs.writeFile(destination, text)
}
console.log(`Imported ${selected.length} explicitly published Markdown notes.`)

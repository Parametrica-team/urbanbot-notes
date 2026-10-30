# URBANBOT Notes

Public Obsidian notes, built with Quartz 4 (MIT) and hosted free on GitHub Pages.

Website: https://parametrica-team.github.io/urbanbot-notes/

## Publish

Add the boolean property `publish: true` to a note in Obsidian. Keep index.md published.
Run from this repository with Node.js 22+ and npm 10.9.2+:

```powershell
npm ci
node scripts/import-vault.mjs "C:\Users\d.sikrier\Documents\OBSIDIAN\URBANBOT"
npx quartz build
git diff -- content
git add content
git commit -m "docs(notes): update published notes"
git push origin main
```

GitHub Actions deploys after each push to main. The vault stays in its existing location.
Only explicitly published Markdown files are imported; private notes never enter this repository.
Images and attachments require separate, explicit addition to content.
Removing publish removes the note from the next import, but previous Git history remains public.
Never copy .obsidian, credentials, internal documentation or the full vault into this public repository.

Upstream: https://github.com/jackyzha0/quartz (v4). The original MIT license is retained.

// Usage:  node setup.mjs <github-username> <repo-name>
// Fills in your GitHub Pages address in the glasses app (two places).
import { readFileSync, writeFileSync } from 'node:fs'

const [user, repo] = process.argv.slice(2)
if (!user || !repo) {
  console.error('Usage: node setup.mjs <github-username> <repo-name>')
  process.exit(1)
}
if (!/^[A-Za-z0-9-]+$/.test(user) || !/^[A-Za-z0-9._-]+$/.test(repo)) {
  console.error('Username or repo name contains unexpected characters.')
  process.exit(1)
}
const u = user.toLowerCase()

let cfg = readFileSync('glasses/src/config.ts', 'utf8')
cfg = cfg.replace(/export const DATA_BASE = '.*'/, `export const DATA_BASE = 'https://${u}.github.io/${repo}/data'`)
writeFileSync('glasses/src/config.ts', cfg)

const app = JSON.parse(readFileSync('glasses/app.json', 'utf8'))
app.permissions[0].whitelist = [`https://${u}.github.io`]
writeFileSync('glasses/app.json', JSON.stringify(app, null, 2) + '\n')

console.log(`Done. Your data address is https://${u}.github.io/${repo}/data`)

// Static build for Vercel: browser client + Pyodide runtime + the Python package.
// No bundler and no network at build time beyond `npm install` of pyodide.
import {cpSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync, existsSync} from 'node:fs';
import {dirname, join, relative} from 'node:path';
import {fileURLToPath} from 'node:url';

const web = dirname(fileURLToPath(import.meta.url));
const root = join(web, '..');
const dist = join(web, 'dist');
const browser = join(root, 'src', 'dimensional_sim', 'world', 'browser');
const pyodide = join(web, 'node_modules', 'pyodide');

rmSync(dist, {recursive: true, force: true});
mkdirSync(dist, {recursive: true});

// 1. Browser client, shared with the local Python server.
for (const name of readdirSync(browser)) {
  if (name === 'index.html') continue;
  cpSync(join(browser, name), join(dist, name));
}
const html = readFileSync(join(browser, 'index.html'), 'utf8')
  .replace('<script type="module" src="/app.js"></script>',
    '<script type="module" src="/host.js"></script>')
  .replace('<link rel="stylesheet" href="/style.css">',
    '<link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/host.css">'
    + '<link rel="manifest" href="/manifest.webmanifest">');
if (!html.includes('/host.js')) throw new Error('index.html script tag changed; update build.mjs');
writeFileSync(join(dist, 'index.html'), html);

// 2. Hosted-mode glue (worker, saves, overlays).
cpSync(join(web, 'src'), dist, {recursive: true});

// 3. Pyodide runtime, served from our own domain.
if (!existsSync(join(pyodide, 'pyodide.js'))) throw new Error('pyodide missing: run npm install in web/');
mkdirSync(join(dist, 'pyodide'));
for (const name of ['pyodide.js', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json', 'pyodide.mjs']) {
  if (existsSync(join(pyodide, name))) cpSync(join(pyodide, name), join(dist, 'pyodide', name));
}

// 4. The Python package (source files) plus a manifest the worker loads.
const pkg = join(root, 'src', 'dimensional_sim');
const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) { if (name !== '__pycache__' && name !== 'browser') walk(path); }
    else if (name.endsWith('.py')) files.push(relative(join(root, 'src'), path).split('\\').join('/'));
  }
})(pkg);
files.sort();
for (const file of files) {
  mkdirSync(dirname(join(dist, 'py', file)), {recursive: true});
  cpSync(join(root, 'src', file), join(dist, 'py', file));
}
const version = JSON.parse(readFileSync(join(web, 'package.json'), 'utf8')).version;
writeFileSync(join(dist, 'py', 'manifest.json'), JSON.stringify({version, built: new Date().toISOString(), files}));
console.log(`dimsum web build: ${files.length} python files, pyodide ${JSON.parse(readFileSync(join(pyodide, 'package.json'), 'utf8')).version}`);

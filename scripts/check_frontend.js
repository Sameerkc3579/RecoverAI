// Compile every JSX file the dashboard loads, with the same Babel version the
// browser uses (pinned in dashboard.html), so a syntax error fails CI instead
// of blanking the page in production.
//   npm install --no-save --prefix .ci @babel/standalone@7.24.0
//   BABEL_STANDALONE=.ci/node_modules/@babel/standalone node scripts/check_frontend.js
const fs = require('fs');
const path = require('path');
// Explicit path so a different Babel in a parent node_modules can't be picked up
const Babel = require(process.env.BABEL_STANDALONE ? path.resolve(process.env.BABEL_STANDALONE) : '@babel/standalone');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'dashboard.html'), 'utf8');

const pinned = /@babel\/standalone@([\d.]+)/.exec(html);
if (pinned && pinned[1] !== Babel.version) {
  console.error(`dashboard.html pins Babel ${pinned[1]} but ${Babel.version} is installed`);
  process.exit(1);
}

const jsx = [...html.matchAll(/<script type="text\/babel" src="\/(static\/[^"?]+)/g)].map(m => m[1]);
const plain = [...html.matchAll(/<script src="\/(static\/[^"?]+)/g)].map(m => m[1]);
let failed = 0;

for (const file of jsx) {
  try {
    Babel.transform(fs.readFileSync(path.join(root, file), 'utf8'), { presets: ['react', 'env'], filename: file });
    console.log('ok  ', file);
  } catch (e) {
    failed++;
    console.error('FAIL', file, '\n     ', e.message.split('\n')[0]);
  }
}
for (const file of plain) {
  try {
    new Function(fs.readFileSync(path.join(root, file), 'utf8'));
    console.log('ok  ', file);
  } catch (e) {
    failed++;
    console.error('FAIL', file, '\n     ', e.message);
  }
}

if (!jsx.length) { console.error('no components found in dashboard.html'); process.exit(1); }
console.log(failed ? `\n${failed} file(s) failed to compile` : `\nall ${jsx.length + plain.length} files compile`);
process.exit(failed ? 1 : 0);

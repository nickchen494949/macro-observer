'use strict';

const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawnSync } = require('child_process');

const REPO_DIR = path.resolve(__dirname, '..');
const JOB_DIR = path.join(REPO_DIR, 'remote_jobs');
const RESULT_DIR = path.join(REPO_DIR, 'remote_results');
const BRANCH = process.env.MACRO_BRANCH || 'agent/phase4-composite-validation';
const RUNNER_VERSION = 1;
const MAX_OUTPUT = 100000;
const DEFAULT_TIMEOUT_MS = 60000;
const MAX_TIMEOUT_MS = 300000;

fs.mkdirSync(JOB_DIR, { recursive: true });
fs.mkdirSync(RESULT_DIR, { recursive: true });

function nowIso() {
  return new Date().toISOString();
}

function truncate(s) {
  s = s == null ? '' : String(s);
  return s.length > MAX_OUTPUT ? s.slice(0, MAX_OUTPUT) + '\n...[truncated]...' : s;
}

function secretValues() {
  const out = [];
  const envPath = path.join(REPO_DIR, '.env');
  try {
    const txt = fs.readFileSync(envPath, 'utf8');
    for (const line of txt.split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
      if (!m) continue;
      const key = m[1];
      let value = m[2].replace(/^['"]|['"]$/g, '');
      if (/(TOKEN|KEY|SECRET|PASSWORD|PASS|CREDENTIAL)/i.test(key) && value.length >= 6) out.push(value);
    }
  } catch (_) {}
  return out;
}

const SECRETS = secretValues();
function redact(s) {
  let out = truncate(s);
  for (const v of SECRETS) out = out.split(v).join('[REDACTED]');
  out = out.replace(/\bghp_[A-Za-z0-9]{20,}\b/g, '[REDACTED_GITHUB_TOKEN]');
  out = out.replace(/\bgithub_pat_[A-Za-z0-9_]{20,}\b/g, '[REDACTED_GITHUB_TOKEN]');
  out = out.replace(/\bsk-[A-Za-z0-9_-]{20,}\b/g, '[REDACTED_API_KEY]');
  return out;
}

function run(exe, args, timeoutMs) {
  const r = spawnSync(exe, args, {
    cwd: REPO_DIR,
    encoding: 'utf8',
    timeout: Math.min(Math.max(Number(timeoutMs) || DEFAULT_TIMEOUT_MS, 1000), MAX_TIMEOUT_MS),
    maxBuffer: 2 * 1024 * 1024,
    env: process.env,
  });
  return {
    exitCode: Number.isInteger(r.status) ? r.status : 1,
    signal: r.signal || null,
    error: r.error ? String(r.error.message || r.error) : null,
    stdout: redact(r.stdout || ''),
    stderr: redact(r.stderr || ''),
  };
}

function git(args, timeoutMs = 30000) {
  return run('git', args, timeoutMs);
}

function safeRepoFile(rel, allowedExts) {
  if (typeof rel !== 'string' || !rel || rel.includes('\0') || path.isAbsolute(rel)) {
    throw new Error('Invalid repository-relative path');
  }
  const normalized = path.normalize(rel);
  if (normalized === '..' || normalized.startsWith('..' + path.sep)) throw new Error('Path escapes repository');
  const full = path.resolve(REPO_DIR, normalized);
  if (!(full === REPO_DIR || full.startsWith(REPO_DIR + path.sep))) throw new Error('Path escapes repository');
  const first = normalized.split(path.sep)[0];
  if (['.git', 'node_modules', 'data', 'csv', 'remote_jobs', 'remote_results'].includes(first)) {
    throw new Error('Path is outside allowed code/test areas');
  }
  if (allowedExts && !allowedExts.includes(path.extname(full).toLowerCase())) {
    throw new Error('File extension is not allowed');
  }
  if (!fs.existsSync(full) || !fs.statSync(full).isFile()) throw new Error('File not found');
  return full;
}

function safeArgs(args) {
  if (args == null) return [];
  if (!Array.isArray(args) || args.length > 30) throw new Error('args must be an array of at most 30 strings');
  return args.map(v => {
    if (typeof v !== 'string' || v.length > 1000 || v.includes('\0')) throw new Error('Invalid argument');
    return v;
  });
}

function localGet(urlPath, timeoutMs) {
  return new Promise(resolve => {
    if (typeof urlPath !== 'string' || !/^\/(health|api\/[A-Za-z0-9_./?=&%+:-]*)$/.test(urlPath)) {
      resolve({ exitCode: 2, signal: null, error: 'Only localhost /health and /api/* GETs are allowed', stdout: '', stderr: '' });
      return;
    }
    const req = http.get({ hostname: '127.0.0.1', port: 8765, path: urlPath, timeout: Math.min(Number(timeoutMs) || 15000, 30000) }, res => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', c => { if (body.length < MAX_OUTPUT) body += c; });
      res.on('end', () => resolve({
        exitCode: res.statusCode >= 200 && res.statusCode < 400 ? 0 : 1,
        signal: null,
        error: null,
        stdout: redact(`HTTP ${res.statusCode}\n${body}`),
        stderr: '',
      }));
    });
    req.on('timeout', () => req.destroy(new Error('HTTP timeout')));
    req.on('error', err => resolve({ exitCode: 1, signal: null, error: String(err.message || err), stdout: '', stderr: '' }));
  });
}

async function executeJob(job) {
  const timeoutMs = Math.min(Math.max(Number(job.timeoutMs) || DEFAULT_TIMEOUT_MS, 1000), MAX_TIMEOUT_MS);

  switch (job.action) {
    case 'health':
      return localGet('/health', timeoutMs);

    case 'api_get':
      return localGet(job.path, timeoutMs);

    case 'git_status': {
      const s = git(['status', '--short'], timeoutMs);
      const l = git(['log', '-1', '--oneline'], timeoutMs);
      return {
        exitCode: s.exitCode || l.exitCode,
        signal: s.signal || l.signal,
        error: s.error || l.error,
        stdout: redact(`HEAD: ${l.stdout.trim()}\nSTATUS:\n${s.stdout}`),
        stderr: redact([s.stderr, l.stderr].filter(Boolean).join('\n')),
      };
    }

    case 'node_check': {
      const files = Array.isArray(job.files) ? job.files : [];
      if (files.length < 1 || files.length > 30) throw new Error('node_check requires 1-30 files');
      const chunks = [];
      let code = 0;
      for (const rel of files) {
        const full = safeRepoFile(rel, ['.js', '.cjs', '.mjs']);
        const r = run(process.execPath, ['--check', full], timeoutMs);
        chunks.push(`## ${rel}\nexit=${r.exitCode}\n${r.stdout}${r.stderr}`);
        if (r.exitCode !== 0) code = r.exitCode;
      }
      return { exitCode: code, signal: null, error: null, stdout: redact(chunks.join('\n')), stderr: '' };
    }

    case 'node_script': {
      const full = safeRepoFile(job.path, ['.js', '.cjs', '.mjs']);
      return run(process.execPath, [full, ...safeArgs(job.args)], timeoutMs);
    }

    case 'python_script': {
      const full = safeRepoFile(job.path, ['.py']);
      return run('python3', [full, ...safeArgs(job.args)], timeoutMs);
    }

    case 'npm_script': {
      const pkg = JSON.parse(fs.readFileSync(path.join(REPO_DIR, 'package.json'), 'utf8'));
      const script = job.script;
      if (typeof script !== 'string' || !pkg.scripts || !Object.prototype.hasOwnProperty.call(pkg.scripts, script)) {
        throw new Error('Unknown npm script');
      }
      if (['start', 'dev'].includes(script)) throw new Error('Long-running npm scripts are not allowed through remote runner');
      return run('npm', ['run', script, '--', ...safeArgs(job.args)], timeoutMs);
    }

    default:
      throw new Error(`Action not allowed: ${job.action}`);
  }
}

function resultPathFor(jobId) {
  if (!/^[A-Za-z0-9._-]{1,120}$/.test(jobId)) throw new Error('Invalid job id');
  return path.join(RESULT_DIR, `${jobId}.json`);
}

function publishResult(relResultPath, jobId) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    let r = git(['add', '--', relResultPath]);
    if (r.exitCode !== 0) return { ok: false, error: `git add failed: ${r.stderr || r.error || ''}` };

    r = git(['commit', '-m', `Remote runner result: ${jobId}`, '--', relResultPath]);
    if (r.exitCode !== 0) {
      const tracked = git(['ls-files', '--error-unmatch', '--', relResultPath]);
      if (tracked.exitCode === 0 && git(['status', '--porcelain', '--', relResultPath]).stdout.trim() === '') {
        return { ok: true, alreadyCommitted: true };
      }
      return { ok: false, error: `git commit failed: ${r.stderr || r.stdout || r.error || ''}` };
    }

    const push = git(['push', 'origin', `HEAD:${BRANCH}`], 60000);
    if (push.exitCode === 0) return { ok: true };

    // Undo only the result commit we just created, keep the result file, then catch up and retry.
    git(['reset', '--mixed', 'HEAD~1']);
    const pull = git(['pull', '--ff-only', 'origin', BRANCH], 60000);
    if (pull.exitCode !== 0) {
      return { ok: false, error: `push failed and retry pull failed: ${redact(push.stderr)} | ${redact(pull.stderr)}` };
    }
  }
  return { ok: false, error: 'Unable to publish result after 3 attempts' };
}

function unpublishedResultFiles() {
  if (!fs.existsSync(RESULT_DIR)) return [];
  return fs.readdirSync(RESULT_DIR)
    .filter(f => f.endsWith('.json'))
    .map(f => path.join('remote_results', f))
    .filter(rel => git(['status', '--porcelain', '--', rel]).stdout.trim() !== '');
}

async function main() {
  // Crash recovery: if a result was written but not pushed, publish it first.
  const pending = unpublishedResultFiles();
  if (pending.length > 0) {
    const rel = pending[0];
    const jobId = path.basename(rel, '.json');
    const pub = publishResult(rel, jobId);
    if (!pub.ok) process.stderr.write(`remote_runner recovery publish failed: ${pub.error}\n`);
    return;
  }

  const jobs = fs.readdirSync(JOB_DIR).filter(f => f.endsWith('.json')).sort();
  for (const filename of jobs) {
    const jobId = path.basename(filename, '.json');
    const resultPath = resultPathFor(jobId);
    if (fs.existsSync(resultPath)) continue;

    const startedAt = nowIso();
    const startedMs = Date.now();
    const headBefore = git(['rev-parse', '--short=12', 'HEAD']).stdout.trim();
    let job = null;
    let execResult;
    try {
      job = JSON.parse(fs.readFileSync(path.join(JOB_DIR, filename), 'utf8'));
      if (job.id !== jobId) throw new Error('job.id must match filename');
      if (job.enabled !== true) throw new Error('Job is not enabled');
      execResult = await executeJob(job);
    } catch (err) {
      execResult = { exitCode: 2, signal: null, error: String(err.message || err), stdout: '', stderr: '' };
    }

    const codeStatus = git(['status', '--short', '--', '.', ':(exclude)data/**', ':(exclude)csv/**', ':(exclude)remote_results/**']).stdout;
    const result = {
      runnerVersion: RUNNER_VERSION,
      jobId,
      action: job && job.action ? job.action : null,
      status: execResult.exitCode === 0 ? 'passed' : (execResult.exitCode === 2 ? 'rejected' : 'failed'),
      exitCode: execResult.exitCode,
      signal: execResult.signal || null,
      error: redact(execResult.error || ''),
      stdout: redact(execResult.stdout || ''),
      stderr: redact(execResult.stderr || ''),
      startedAt,
      finishedAt: nowIso(),
      durationMs: Date.now() - startedMs,
      localHeadBefore: headBefore,
      codeWorktreeStatusAfter: redact(codeStatus),
    };

    fs.writeFileSync(resultPath, JSON.stringify(result, null, 2) + '\n');
    const rel = path.relative(REPO_DIR, resultPath);
    const pub = publishResult(rel, jobId);
    if (!pub.ok) process.stderr.write(`remote_runner publish failed for ${jobId}: ${pub.error}\n`);
    return; // one job per 30-second cycle
  }
}

main().catch(err => {
  process.stderr.write(`remote_runner fatal: ${redact(err && err.stack ? err.stack : err)}\n`);
  process.exitCode = 1;
});

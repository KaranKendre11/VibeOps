import { useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { motion } from 'framer-motion';
import { api, ApiError } from '../api/client';
import { useStore } from '../store/useStore';
import { Panel } from '../components/Panel';
import { Button } from '../components/Button';
import { ScrambleReveal } from '../components/scramble';
import { Select } from '../components/Select';
import {
  FieldError,
  FieldHint,
  Label,
  TextArea,
  TextInput,
} from '../components/Field';
import { cn, usd } from '../lib/utils';
import { useParallax } from '../lib/useParallax';

type Step = 1 | 2 | 3;

const STEP_TITLES: Record<Step, string> = {
  1: 'OpenAI API key',
  2: 'GCP service account',
  3: 'Project & budget',
};

export function SetupScreen() {
  const config = useStore((s) => s.config);
  const completeSetup = useStore((s) => s.completeSetup);

  const parallax = useParallax(10);

  const [step, setStep] = useState<Step>(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // step 1
  const [openaiKey, setOpenaiKey] = useState('');
  const [openaiMsg, setOpenaiMsg] = useState<string | null>(null);

  // step 2
  const [saText, setSaText] = useState('');
  const [gcpMsg, setGcpMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // step 3
  const [projects, setProjects] = useState<string[]>([]);
  const [project, setProject] = useState<string | undefined>(undefined);
  const [capText, setCapText] = useState('');

  const capValue = capText.trim()
    ? Number(capText)
    : (config?.default_cost_cap_usd ?? 200);

  async function submitOpenAI() {
    setError(null);
    setBusy(true);
    try {
      const res = await api.validateOpenAI(openaiKey.trim());
      if (!res.ok) {
        setError(res.message || 'Key rejected.');
        return;
      }
      setOpenaiMsg(res.fingerprint ? `Verified · ${res.fingerprint}` : res.message);
      setStep(2);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Validation failed.');
    } finally {
      setBusy(false);
    }
  }

  async function submitGcp() {
    setError(null);
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(saText);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        throw new Error('not-object');
      }
    } catch {
      setError('That is not valid service-account JSON.');
      return;
    }
    setBusy(true);
    try {
      const res = await api.validateGcp(parsed);
      if (!res.ok) {
        setError(res.message || 'Credentials rejected.');
        return;
      }
      setGcpMsg(res.fingerprint ? `Verified · ${res.fingerprint}` : res.message);
      const list = await api.listProjects();
      setProjects(list.project_ids);
      setProject(list.project_ids[0]);
      setCapText(String(config?.default_cost_cap_usd ?? 200));
      setStep(3);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Validation failed.');
    } finally {
      setBusy(false);
    }
  }

  async function launch() {
    if (!project) {
      setError('Pick a project.');
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const res = await api.completeSetup(project, capValue);
      if (!res.ok) {
        setError('Setup could not be completed — re-check your credentials.');
        return;
      }
      completeSetup({ demo: false, costCap: capValue });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Setup failed.');
    } finally {
      setBusy(false);
    }
  }

  async function tryDemo() {
    setError(null);
    setBusy(true);
    try {
      const res = await api.startDemo();
      completeSetup({
        demo: true,
        threadId: res.thread_id,
        costCap: config?.default_cost_cap_usd ?? undefined,
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start demo.');
    } finally {
      setBusy(false);
    }
  }

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    file.text().then((t) => setSaText(t));
  }

  return (
    <div className="mx-auto flex min-h-[72vh] max-w-2xl flex-col justify-center px-4 py-12">
      <motion.div className="mb-8 text-center" style={{ x: parallax.x, y: parallax.y }}>
        <ScrambleReveal text="Get started" className="text-meta !text-accent" />
        <h1 className="mt-4 text-3xl font-semibold sm:text-4xl">
          <ScrambleReveal text="Connect your cloud" />
        </h1>
        <p className="mx-auto mt-4 max-w-lg font-light text-fg-muted">
          Connect your keys to let the agent operate your cloud — or explore in demo mode.
        </p>
      </motion.div>

      {/* step rail */}
      <div className="mb-6 flex items-center justify-center gap-2">
        {([1, 2, 3] as Step[]).map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={cn(
                'grid h-7 w-7 place-items-center rounded-full border font-mono text-xs transition-colors',
                s === step
                  ? 'border-accent text-accent shadow-glow-sm'
                  : s < step
                    ? 'border-accent/50 bg-accent/10 text-accent'
                    : 'border-line text-fg-dim',
              )}
            >
              {s < step ? '✓' : s}
            </div>
            {s < 3 && <span className={cn('h-px w-8', s < step ? 'bg-accent/50' : 'bg-line')} />}
          </div>
        ))}
      </div>

      <Panel glow className="p-6 sm:p-8">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        >
          <h2 className="mb-1 font-mono text-xs uppercase tracking-[0.2em] text-accent">
            Step {step} / 3
          </h2>
          <h3 className="mb-6 text-2xl font-semibold">
            <ScrambleReveal text={STEP_TITLES[step]} />
          </h3>

          {step === 1 && (
            <div>
              <Label htmlFor="openai">API key</Label>
              <TextInput
                id="openai"
                type="password"
                autoComplete="off"
                placeholder="sk-…"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && openaiKey.trim() && submitOpenAI()}
              />
              <FieldHint>
                Used only in your session, in server memory. Never written to disk.
              </FieldHint>
              <FieldError>{error}</FieldError>
              <div className="mt-6 flex justify-end">
                <Button onClick={submitOpenAI} loading={busy} disabled={!openaiKey.trim()}>
                  Validate & continue
                </Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              {openaiMsg && (
                <p className="mb-4 rounded-sm border border-accent/30 bg-accent/5 px-3 py-2 text-xs text-accent">
                  OpenAI {openaiMsg}
                </p>
              )}
              <div className="mb-2 flex items-center justify-between">
                <Label htmlFor="gcp">Service-account JSON</Label>
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="font-mono text-[11px] uppercase tracking-[0.15em] text-accent hover:underline"
                >
                  Upload file
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={onFile}
                />
              </div>
              <TextArea
                id="gcp"
                rows={8}
                spellCheck={false}
                placeholder='{ "type": "service_account", "project_id": "…", … }'
                value={saText}
                onChange={(e) => setSaText(e.target.value)}
                className="font-mono text-xs"
              />
              <FieldHint>Paste the JSON or upload the key file. Stays in-session only.</FieldHint>
              <FieldError>{error}</FieldError>
              <div className="mt-6 flex justify-between">
                <Button variant="ghost" onClick={() => setStep(1)} disabled={busy}>
                  Back
                </Button>
                <Button onClick={submitGcp} loading={busy} disabled={!saText.trim()}>
                  Validate & continue
                </Button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              {gcpMsg && (
                <p className="mb-4 rounded-sm border border-accent/30 bg-accent/5 px-3 py-2 text-xs text-accent">
                  GCP {gcpMsg}
                </p>
              )}
              <Label htmlFor="project">Project</Label>
              <Select
                id="project"
                value={project}
                onChange={setProject}
                placeholder={projects.length ? 'Choose a project' : 'No projects found'}
                options={projects.map((p) => ({ value: p, label: p }))}
                disabled={projects.length === 0}
              />

              <div className="mt-5">
                <Label htmlFor="cap">Monthly cost cap (USD)</Label>
                <TextInput
                  id="cap"
                  type="number"
                  min={1}
                  step={10}
                  value={capText}
                  onChange={(e) => setCapText(e.target.value)}
                />
                <FieldHint>
                  The agent blocks deploys whose estimate exceeds this cap. Currently{' '}
                  <span className="text-accent">{usd(capValue)}</span>/mo.
                </FieldHint>
              </div>

              <FieldError>{error}</FieldError>
              <div className="mt-6 flex justify-between">
                <Button variant="ghost" onClick={() => setStep(2)} disabled={busy}>
                  Back
                </Button>
                <Button size="lg" onClick={launch} loading={busy} disabled={!project}>
                  Launch →
                </Button>
              </div>
            </div>
          )}
        </motion.div>
      </Panel>

      <div className="my-6 flex items-center gap-4 text-fg-dim">
        <span className="h-px flex-1 bg-line" />
        <span className="font-mono text-[11px] uppercase tracking-[0.2em]">or</span>
        <span className="h-px flex-1 bg-line" />
      </div>

      <Button variant="secondary" size="lg" onClick={tryDemo} loading={busy} className="w-full">
        ▶ Try the live demo — no credentials needed
      </Button>
      <p className="mt-3 text-center text-xs text-fg-dim">
        Walk the full flow with representative data — deploy is simulated, so no real cloud
        resources are created.
      </p>
    </div>
  );
}

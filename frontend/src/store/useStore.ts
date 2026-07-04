import { create } from 'zustand';
import type { AppConfig, GraphState, Snapshot, Stage } from '../api/types';

// ---------------------------------------------------------------------------
// Interactive progress rail — pipeline model + guarded navigation.
// Plain VibeOps terms (no space/"mission" theme).
// ---------------------------------------------------------------------------

export type StepKey = 'describe' | 'plan' | 'review' | 'deploy' | 'live';

export interface JourneyStep {
  key: StepKey;
  label: string;
  /** The store `stage` this step maps to when the user navigates to it. */
  stage: Stage;
}

/** Canonical ordered pipeline. Array index === position in the rail. */
export const JOURNEY_STEPS: JourneyStep[] = [
  { key: 'describe', label: 'Describe', stage: 'chat' },
  { key: 'plan', label: 'Plan', stage: 'architecture' },
  { key: 'review', label: 'Review', stage: 'review' },
  { key: 'deploy', label: 'Deploy', stage: 'deployment' },
  { key: 'live', label: 'Live', stage: 'done' },
];

/** Index at/after which a real deployment has started (resources may exist). */
const DEPLOY_INDEX = JOURNEY_STEPS.findIndex((s) => s.key === 'deploy'); // 3

/** Map a graph `stage` to its rail index. `cancelled` is shown at the Review node. */
export function stepIndexForStage(stage: Stage): number {
  switch (stage) {
    case 'architecture':
      return 1;
    case 'review':
    case 'cancelled':
      return 2;
    case 'deployment':
      return 3;
    case 'done':
      return 4;
    default:
      return 0; // idle | chat
  }
}

/** Outcome of asking whether the user may click a given rail step. */
export type NavDecision =
  | { kind: 'current' }
  | { kind: 'allowed' }
  | { kind: 'blocked'; reason: string }
  | { kind: 'warn'; title: string; message: string; confirmLabel: string };

function forwardBlocked(step: JourneyStep): NavDecision {
  return {
    kind: 'blocked',
    reason: `${step.label} isn't available yet — finish the current step first.`,
  };
}

function postDeployBlocked(step: JourneyStep): NavDecision {
  const reason =
    step.key === 'deploy'
      ? 'Deployment has already run. Tear down the resources before deploying again.'
      : 'Your infrastructure is live, so earlier steps are locked. Tear it down from the Deploy screen to start over.';
  return { kind: 'blocked', reason };
}

function backwardWarn(step: JourneyStep): NavDecision {
  if (step.key === 'describe') {
    return {
      kind: 'warn',
      title: 'Return to Describe?',
      message:
        'Your current plan stays on screen while you look. But sending a new request will discard the ' +
        'generated architecture, Terraform, and cost estimate and start over.',
      confirmLabel: 'Return to Describe',
    };
  }
  if (step.key === 'plan') {
    return {
      kind: 'warn',
      title: 'Back to machine selection?',
      message:
        'You can review the discovered machines again. Confirming a machine regenerates the Terraform ' +
        'and cost estimate, discarding any edits you made in Review.',
      confirmLabel: 'Back to Plan',
    };
  }
  // Only describe/plan are ever backward targets before deploy; allow otherwise.
  return { kind: 'allowed' };
}

interface AppStore {
  // boot
  booted: boolean;
  bootError: string | null;
  config: AppConfig | null;
  threadId: string | null;

  // landing gate — the cinematic marketing landing shows until the user clicks "Try it".
  entered: boolean;

  // setup gate
  setupComplete: boolean;
  demoMode: boolean;
  costCap: number | null;

  // graph
  stage: Stage;
  graph: GraphState | null;

  // navigation — furthest rail index the real flow has reached (monotonic per run).
  maxReached: number;

  // ui
  inventoryOpen: boolean;

  // actions
  setBoot: (payload: { config: AppConfig; threadId: string }) => void;
  setBootError: (message: string) => void;
  /** Leave the landing page and enter the product (setup screen). */
  enterApp: () => void;
  /** Return to the marketing landing page (session state is kept). */
  exitToLanding: () => void;
  completeSetup: (opts: { demo: boolean; threadId?: string; costCap?: number }) => void;
  applySnapshot: (snapshot: Snapshot) => void;
  setStage: (stage: Stage) => void;
  setInventoryOpen: (open: boolean) => void;
  /** Decide whether clicking `target` on the rail is allowed / blocked / warned. */
  canNavigate: (target: StepKey) => NavDecision;
  /** UI-only navigation to an already-reached step (never re-runs the graph). */
  navigateTo: (target: StepKey) => void;
  /**
   * Start a fresh plan WITHIN the app: clear the run/graph state and drop back to the
   * first pipeline step (Describe), keeping credentials + setup. Powers "Start over".
   */
  resetPlan: () => void;
  /**
   * Full client-side wipe (credentials, setup, and plan). Pairs with
   * ``api.resetCredentials()`` + ``exitToLanding()`` for the "clear credentials & exit"
   * control; on re-entry the user goes back through setup.
   */
  reset: () => void;
}

export const useStore = create<AppStore>((set, get) => ({
  booted: false,
  bootError: null,
  config: null,
  threadId: null,

  entered: false,

  setupComplete: false,
  demoMode: false,
  costCap: null,

  stage: 'idle',
  graph: null,

  maxReached: 0,

  inventoryOpen: false,

  setBoot: ({ config, threadId }) =>
    set({ booted: true, bootError: null, config, threadId }),
  setBootError: (message) => set({ booted: true, bootError: message }),
  enterApp: () => set({ entered: true }),
  exitToLanding: () => set({ entered: false }),
  completeSetup: ({ demo, threadId, costCap }) =>
    set((s) => ({
      setupComplete: true,
      demoMode: demo,
      threadId: threadId ?? s.threadId,
      costCap: costCap ?? s.costCap ?? s.config?.default_cost_cap_usd ?? null,
      stage: 'idle',
      maxReached: 0,
    })),
  applySnapshot: (snapshot) =>
    set((s) => ({
      stage: snapshot.stage,
      graph: snapshot.state,
      // Forward progress from the real graph is monotonic; UI navigation never lowers it.
      maxReached: Math.max(s.maxReached, stepIndexForStage(snapshot.stage)),
    })),
  setStage: (stage) =>
    set((s) => ({ stage, maxReached: Math.max(s.maxReached, stepIndexForStage(stage)) })),
  setInventoryOpen: (open) => set({ inventoryOpen: open }),

  canNavigate: (target) => {
    const { stage, maxReached } = get();
    const active = stepIndexForStage(stage);
    const targetIndex = JOURNEY_STEPS.findIndex((s) => s.key === target);
    const step = JOURNEY_STEPS[targetIndex];
    if (!step) return { kind: 'blocked', reason: 'Unknown step.' };
    if (targetIndex === active) return { kind: 'current' };

    // Forward — only to a step the flow has already reached (can't skip ahead).
    if (targetIndex > active) {
      return targetIndex <= maxReached ? { kind: 'allowed' } : forwardBlocked(step);
    }

    // Backward — locked once a deployment has started / resources may be live.
    if (maxReached >= DEPLOY_INDEX) return postDeployBlocked(step);

    // Pre-deploy backward — navigation itself is safe; warn where acting regenerates work.
    return backwardWarn(step);
  },

  navigateTo: (target) => {
    const decision = get().canNavigate(target);
    if (decision.kind === 'blocked' || decision.kind === 'current') return;
    const step = JOURNEY_STEPS.find((s) => s.key === target);
    if (step) set({ stage: step.stage }); // stage only — graph state is untouched.
  },

  resetPlan: () =>
    // Keep setupComplete/demoMode/costCap/credentials — only the plan is discarded.
    // stage:'idle' lands on the Describe screen, where a new plan begins.
    set({ stage: 'idle', graph: null, maxReached: 0 }),

  reset: () =>
    set({
      setupComplete: false,
      demoMode: false,
      stage: 'idle',
      graph: null,
      maxReached: 0,
    }),
}));

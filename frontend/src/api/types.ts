// Types mirroring the FastAPI backend contract (src/vibeops/api + models).
// Fields are intentionally permissive / optional where the live backend shape
// differs slightly from the documented contract, so the UI degrades gracefully.

export type Stage =
  | 'idle'
  | 'chat'
  | 'architecture'
  | 'review'
  | 'deployment'
  | 'cancelled'
  | 'done';

export type DeploymentPhase =
  | 'idle'
  | 'planning'
  | 'applying'
  | 'succeeded'
  | 'failed'
  | 'awaiting_destroy_confirm'
  | 'destroying'
  | 'destroyed'
  | 'cancelled';

export interface AppConfig {
  default_model: string;
  default_cost_cap_usd: number;
}

export interface ValidateResult {
  ok: boolean;
  message: string;
  fingerprint?: string | null;
}

export type TurnRole = 'user' | 'agent' | string;

export interface ConversationTurn {
  role: TurnRole;
  content: string;
}

export interface ArchitectureCandidate {
  zone: string;
  region?: string;
  machine_type: string;
  // Backend uses cpus/memory_gb; contract doc used vcpus/ram_gb — accept both.
  cpus?: number;
  vcpus?: number;
  memory_gb?: number;
  ram_gb?: number;
  gpu_type?: string;
  quota_total: number;
  quota_remaining: number;
  rationale: string;
}

export interface NetworkObject {
  name: string;
  self_link?: string;
  auto_create_subnetworks?: boolean;
}

export type NetworkOption = string | NetworkObject;

export interface ArchitectureOptions {
  candidates: ArchitectureCandidate[];
  networks: NetworkOption[];
  requirement?: Record<string, unknown> & { gpu_type?: string };
}

export interface ComputeSpec {
  machine_type: string;
  zone: string;
  gpu_type: string;
  gpu_count: number;
  preemptible: boolean;
}

export interface StorageSpec {
  disk_size_gb: number;
  os_image_family: string;
  os_image_project?: string;
}

export interface NetworkSpec {
  network_name: string;
  open_ports: number[];
  create_external_ip: boolean;
}

export interface DeploymentSpec {
  compute: ComputeSpec;
  storage: StorageSpec;
  network: NetworkSpec;
  project_id: string;
  app?: Record<string, unknown>;
}

export interface CostLineItem {
  description: string;
  hourly_usd: number;
  monthly_usd: number;
}

export interface CostEstimate {
  monthly_usd: number;
  hourly_usd: number;
  source: string;
  confidence?: string;
  breakdown: CostLineItem[];
  notes: string[];
}

export interface StateResource {
  type: string;
  name: string;
  zone?: string | null;
  provider?: string | null;
}

export interface GraphState {
  user_prompt: string;
  conversation: ConversationTurn[];
  architecture_options: ArchitectureOptions | null;
  deployment_spec: DeploymentSpec | null;
  terraform_files: Record<string, string>;
  cost_estimate: CostEstimate | null;
  cost_estimate_stale?: boolean;
  cost_cap_exceeded: boolean;
  validation_errors: string[];
  deployment_phase: DeploymentPhase;
  deployment_logs: string[];
  created_resources: StateResource[];
  deployment_error: string | null;
  stage?: string;
  [key: string]: unknown;
}

export interface Snapshot {
  stage: Stage;
  state: GraphState;
}

export interface RunningInstance {
  name: string;
  zone: string;
  machine_type: string;
  status: string;
  internal_ip?: string;
  external_ip?: string;
  creation_timestamp?: string;
  labels?: Record<string, string>;
  gpu_summary?: string;
}

export interface InventoryResult {
  available: boolean;
  instances: RunningInstance[];
}

// SSE frame shapes
export interface ChatTokenFrame {
  token: string;
}
export interface ChatDoneFrame {
  done: true;
  proceed: boolean;
  message: string;
  stage: Stage;
}
export type ChatFrame = ChatTokenFrame | ChatDoneFrame;

export interface LogFrame {
  log: string;
}
export interface LogDoneFrame {
  done: true;
  stage?: Stage;
  phase?: DeploymentPhase;
  error?: string;
}
export type DeployFrame = LogFrame | LogDoneFrame;

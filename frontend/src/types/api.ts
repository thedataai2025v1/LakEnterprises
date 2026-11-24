/**
 * LakEnterprises Console UI Shell — Domain Types and API Contracts
 */

export type UserRole = 'viewer' | 'analyst' | 'admin';

export interface UserProfile {
  id: string;
  username: string;
  role?: UserRole;
  roles?: string[];
  permissions?: string[];
  email?: string;
  tenant_id?: string;
  is_authenticated?: boolean;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export interface HealthStatus {
  status: string;
  database?: string;
  service?: string;
  version?: string;
}

export interface ProcessTemplate {
  id: string;
  name: string;
  version: string;
  description?: string;
  steps: string[];
  created_at?: string;
}

export type ProcessStatus = 
  | 'PENDING' 
  | 'RUNNING' 
  | 'PAUSED' 
  | 'AWAITING_APPROVAL' 
  | 'COMPLETED' 
  | 'FAILED' 
  | 'REJECTED';

export interface ProcessInstance {
  id: string;
  template_id?: string;
  title: string;
  status: ProcessStatus;
  current_step?: string;
  initiator?: string;
  context?: Record<string, any>;
  risk_score?: number;
  created_at: string;
  updated_at: string;
}

export interface ProcessTask {
  id: string;
  process_id: string;
  title: string;
  assignee_role?: string;
  status: string;
  created_at: string;
}

export interface ApprovalRequest {
  id: string;
  process_id: string;
  amount?: number;
  urgency?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  reason?: string;
  escalation_tier?: 'TIER_1_ANALYST' | 'TIER_2_MANAGER' | 'TIER_3_DIRECTOR' | 'TIER_4_EXECUTIVE';
  deadline?: string;
  created_at: string;
}

export interface DocumentMetadata {
  id: string;
  filename: string;
  doc_type?: string;
  chunks_count: number;
  created_at: string;
}

export interface SearchResult {
  content: string;
  score: number;
  source: string;
  locator?: string;
}

export interface WorkflowRunRequest {
  process_id: string;
  input_data: Record<string, any>;
}

export interface WorkflowTraceEvent {
  event_id: string;
  process_id: string;
  node_name: string;
  event_type: string;
  payload: Record<string, any>;
  timestamp: string;
  duration_ms?: number;
}

export interface WorkflowCheckpoint {
  checkpoint_id: string;
  process_id: string;
  node_name: string;
  step_index: number;
  state_snapshot: Record<string, any>;
  timestamp: string;
}

export interface WorkflowSLAMetrics {
  tier: string;
  max_hours: number;
  deadline: string;
  elapsed_hours: number;
  hours_remaining: number;
  is_breached: boolean;
}

export interface WorkflowState {
  process_id: string;
  current_step?: string;
  status?: ProcessStatus;
  instruction?: string;
  title?: string;
  context?: Record<string, any>;
  history?: Array<{
    node: string;
    timestamp: string;
    summary?: string;
    output?: Record<string, any>;
  }>;
  risk_level?: string;
  approval_status?: string;
  escalation_tier?: string;
  resolution_action?: string;
  resolution_result?: Record<string, any>;
  sla?: WorkflowSLAMetrics;
}

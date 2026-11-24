/**
 * LakEnterprises Typed API Client
 * High-performance, error-tolerant fetch client communicating with FastAPI backend (:8001)
 */

import type {
  AuthTokens,
  UserProfile,
  HealthStatus,
  ProcessTemplate,
  ProcessInstance,
  ApprovalRequest,
  DocumentMetadata,
  SearchResult,
  WorkflowState,
} from '../types/api.ts';

export class ApiError extends Error {
  status: number;
  message: string;
  detail?: any;

  constructor(status: number, message: string, detail?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.message = message;
    this.detail = detail;
  }
}

export class LakApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || (typeof window !== 'undefined' ? '' : 'http://127.0.0.1:8001');
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('lak_access_token');
    }
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('lak_access_token', token);
      } else {
        localStorage.removeItem('lak_access_token');
      }
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Request-ID': `client-req-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let detail = null;
      try {
        const errJson = await response.json();
        detail = errJson.detail || errJson;
      } catch {
        // Non-JSON response
      }
      throw new ApiError(
        response.status,
        detail?.message || detail || `API Request failed with status ${response.status}`,
        detail
      );
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  // ── Health ─────────────────────────────────────────────────────────────
  async getHealth(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health/ready');
  }

  // ── Authentication ─────────────────────────────────────────────────────
  async loginDemo(role: 'viewer' | 'analyst' | 'admin'): Promise<AuthTokens> {
    const data = await this.request<AuthTokens>(`/api/v1/auth/demo/${role}`, {
      method: 'POST',
    });
    this.setToken(data.access_token);
    return data;
  }

  async getMe(): Promise<UserProfile> {
    return this.request<UserProfile>('/api/v1/auth/me');
  }

  async logout(): Promise<void> {
    try {
      await this.request('/api/v1/auth/logout', { method: 'POST' });
    } catch {
      // Ignore network errors on logout
    } finally {
      this.setToken(null);
    }
  }

  // ── Processes ──────────────────────────────────────────────────────────
  async listProcesses(): Promise<ProcessInstance[]> {
    return this.request<ProcessInstance[]>('/api/v1/processes/instances');
  }

  async getProcess(id: string): Promise<ProcessInstance> {
    return this.request<ProcessInstance>(`/api/v1/processes/instances/${id}`);
  }

  async listTemplates(): Promise<ProcessTemplate[]> {
    return this.request<ProcessTemplate[]>('/api/v1/processes/templates');
  }

  // ── Approvals & Human-in-the-Loop ──────────────────────────────────────
  async listApprovals(): Promise<ApprovalRequest[]> {
    return this.request<ApprovalRequest[]>('/api/v1/approvals');
  }

  async decideApproval(
    requestId: string,
    decision: 'APPROVED' | 'REJECTED',
    notes?: string
  ): Promise<any> {
    return this.request(`/api/v1/approvals/${requestId}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, notes }),
    });
  }

  // ── Documents & Hybrid Search ──────────────────────────────────────────
  async listDocuments(): Promise<DocumentMetadata[]> {
    return this.request<DocumentMetadata[]>('/api/v1/documents');
  }

  async searchDocuments(query: string, limit: number = 5): Promise<SearchResult[]> {
    return this.request<SearchResult[]>('/api/v1/documents/search', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    });
  }

  // ── Workflow Graph ─────────────────────────────────────────────────────
  async getWorkflowState(processId: string): Promise<WorkflowState> {
    return this.request<WorkflowState>(`/api/v1/workflow/${processId}/state`);
  }

  async resumeWorkflow(processId: string, payload: Record<string, any> = {}): Promise<any> {
    return this.request(`/api/v1/workflow/${processId}/resume`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}

// Export singleton instance
export const api = new LakApiClient();

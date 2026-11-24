import test from 'node:test';
import assert from 'node:assert';
import { LakApiClient } from '../src/lib/api-client.ts';

test('LakApiClient workflow graph endpoints and decision payloads', () => {
  const client = new LakApiClient('http://localhost:8001');

  // Verify client methods exist for Phase 13
  assert.strictEqual(typeof client.getWorkflowState, 'function');
  assert.strictEqual(typeof client.getWorkflowEvents, 'function');
  assert.strictEqual(typeof client.getWorkflowCheckpoints, 'function');
  assert.strictEqual(typeof client.getWorkflowSLA, 'function');
  assert.strictEqual(typeof client.resumeWorkflow, 'function');
  assert.strictEqual(typeof client.decideWorkflowApproval, 'function');
  assert.strictEqual(typeof client.runWorkflow, 'function');
});

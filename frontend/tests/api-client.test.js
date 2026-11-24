import test from 'node:test';
import assert from 'node:assert';
import { LakApiClient } from '../src/lib/api-client.ts';

test('LakApiClient token management and headers', () => {
  const client = new LakApiClient('http://localhost:8001');
  assert.strictEqual(client.getToken(), null);

  client.setToken('test-access-token-12345');
  assert.strictEqual(client.getToken(), 'test-access-token-12345');

  client.setToken(null);
  assert.strictEqual(client.getToken(), null);
});

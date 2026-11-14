import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './App';
import { createPreview } from './preview';
import { createApi, savings } from './api';
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });
describe('support workspace', () => {
  it('asks for context and preserves the same case when the customer replies', async () => {
    const user = userEvent.setup();
    render(<App client={createPreview()} preview onExit={() => {}}/>);
    await user.click(await screen.findByRole('button', { name: /CS-1046/ }));
    await user.click(await screen.findByRole('button', { name: /Run investigation/ }));
    await waitFor(() => expect((screen.getByLabelText('Customer reply') as HTMLInputElement).disabled).toBe(false));
    await user.type(screen.getByLabelText('Customer reply'), 'ORD-2046');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(screen.getAllByText(/Only one completed charge is confirmed/).length).toBeGreaterThan(0));
    expect(screen.getByRole('heading', { name: 'CS-1046' })).toBeTruthy();
    expect(screen.getByText(/TXN-46B: PENDING_AUTHORIZATION/)).toBeTruthy();
  });
  it('does not invent success when the backend rejects a run', async () => {
    const client = createPreview();
    client.run = vi.fn().mockRejectedValue(new Error('Your server-assigned role cannot perform this action.'));
    const user = userEvent.setup();
    render(<App client={client} preview={false} onExit={() => {}}/>);
    await user.click(await screen.findByRole('button', { name: /Run investigation/ }));
    expect((await screen.findByRole('alert')).textContent).toContain('cannot perform');
    expect(screen.queryByText(/Mock refund initiated/)).toBeNull();
  });
  it('requires exact-action confirmation and leaves an approved refund pending', async () => {
    const user = userEvent.setup();
    render(<App client={createPreview()} preview onExit={() => {}}/>);
    await user.click(await screen.findByRole('button', { name: /Run investigation/ }));
    await user.click(await screen.findByRole('button', { name: /Review approval queue/ }));
    await user.click(screen.getByRole('button', { name: 'Review approval' }));
    await user.type(screen.getByLabelText('Approval comment'), 'Duplicate payment verified.');
    await user.click(screen.getByRole('button', { name: 'Confirm approval' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Review approval' })).toBeNull());
    await user.click(screen.getByRole('button', { name: /Case inbox/ }));
    await waitFor(() => expect(screen.getAllByText(/Preview refund completed successfully/).length).toBeGreaterThan(0));
    expect(screen.getByText('succeeded')).toBeTruthy();
  });
  it('never presents browser rehearsal as measured evaluation', async () => {
    const user = userEvent.setup();
    render(<App client={createPreview()} preview onExit={() => {}}/>);
    await screen.findByRole('button', { name: /Run investigation/ });
    await user.click(screen.getByRole('button', { name: /Business impact/ }));
    expect(screen.getByText(/Not yet measured/)).toBeTruthy();
  });
});
describe('preview and transport boundaries', () => {
  it('persists pending approval across refresh and prevents a second refund', async () => {
    const client = createPreview(sessionStorage);
    await client.run('CS-1042');
    const resumed = createPreview(sessionStorage);
    const [approval] = await resumed.approvals();
    await resumed.decide(approval, 'APPROVED', 'Duplicate capture verified.');
    await expect(resumed.decide(approval, 'APPROVED', 'Duplicate capture verified.')).rejects.toThrow();
    expect((await resumed.detail('CS-1042')).status).toBe('RESOLVED');
    expect((await resumed.events('CS-1042')).filter(e => e.stage === 'initiate_mock_refund')).toHaveLength(1);
  });
  it('expires approvals without a write', async () => {
    const client = createPreview();
    await client.run('CS-1042');
    const [a] = await client.approvals();
    vi.spyOn(Date, 'now').mockReturnValue(Date.parse(a.expires_at) + 1);
    await expect(client.decide(a, 'APPROVED', 'Approved after review.')).rejects.toThrow();
    expect((await client.detail('CS-1042')).status).toBe('ESCALATED');
    expect((await client.events('CS-1042')).some(e => e.stage === 'initiate_mock_refund')).toBe(false);
  });
  it('shows context-driven risk, safe retry, pending and rejection paths', async () => {
    const client = createPreview();
    expect((await client.run('RISK-HISTORY-02')).risk_tier).toBe('RED');
    expect(await client.approvals()).toHaveLength(0);
    await client.injectTimeout('CS-1043');
    expect((await client.run('CS-1043')).reflection_revisions).toBe(1);
    expect((await client.events('CS-1043')).filter(e => e.stage === 'reconcile_order')).toHaveLength(1);
    expect((await client.run('CS-1044')).status).toBe('PENDING_EXTERNAL');
    await client.run('CS-1042');
    await client.decide((await client.approvals())[0], 'REJECTED', 'Needs manual review.');
    expect((await client.detail('CS-1042')).refund_ref).toBeUndefined();
  });
  it('uses open local requests, surfaces denial and never retries writes', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{}', { status: 403 }));
    vi.stubGlobal('fetch', fetcher);
    await expect(createApi().run('CS-1043')).rejects.toThrow('not available');
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][1].headers).toBeUndefined();
  });
  it('computes explicitly assumed savings', () => {
    expect(savings(100000, .3)).toEqual({ grossRupees: 1200000, grossHours: 3000 });
    expect(savings(100000, .6).grossRupees).toBe(2400000);
  });
});


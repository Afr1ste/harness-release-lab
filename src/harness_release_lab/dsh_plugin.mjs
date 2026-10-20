// Thin native DSH bridge. All state, faults and assertions live in Python.
export const name = 'harness-release-lab';
export const inject = ['tools'];

export function apply(ctx, config) {
  const url = new URL(config.endpoint);
  if (url.hostname !== '127.0.0.1' || url.protocol !== 'http:') {
    throw new Error('Lab endpoint must be loopback HTTP');
  }
  ctx.tools.register({
    name: 'lab_refund',
    isConcurrencySafe: () => true,
    description: 'Create a refund in the disposable local test ledger.',
    parameters: {
      type: 'object',
      properties: {
        operation_key: { type: 'string' },
        order_id: { type: 'string' },
        amount_cents: { type: 'integer' },
      },
      required: ['operation_key', 'order_id', 'amount_cents'],
      additionalProperties: false,
    },
    output: {
      schema: {
        type: 'object',
        properties: { http_status: { type: 'integer' }, body: { type: 'string' } },
        required: ['http_status', 'body'],
        additionalProperties: false,
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    async execute(args, exec) {
      try {
        const response = await fetch(config.endpoint + '/refund', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + config.token,
            'Idempotency-Key': args.operation_key,
          },
          body: JSON.stringify({ order_id: args.order_id, amount_cents: args.amount_cents }),
          signal: AbortSignal.any([exec.signal, AbortSignal.timeout(config.timeoutMs)]),
        });
        return { http_status: response.status, body: await response.text() };
      } catch (error) {
        if (exec.signal.aborted) throw error;
        if (error.name !== 'TimeoutError') throw error;
        return { http_status: 0, body: 'client deadline exceeded; commit state unknown' };
      }
    },
  });
}

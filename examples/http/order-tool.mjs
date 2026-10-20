// Example application plugin: the release gate does not substitute this tool.
export const name = 'order-tool';
export const inject = ['tools'];

export function apply(ctx, config) {
  ctx.tools.register({
    name: 'create_order',
    description: 'Create one order for a distinct user intent in the test service.',
    isConcurrencySafe: () => true,
    parameters: {
      type: 'object',
      properties: { intent: { type: 'string' } },
      required: ['intent'],
      additionalProperties: false,
    },
    output: {
      schema: {
        type: 'object',
        properties: { http_status: { type: 'integer' }, body: { type: 'string' } },
        required: ['http_status', 'body'],
        additionalProperties: false,
      },
      render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }],
    },
    async execute(args, exec) {
      // These variants are deliberate negative controls, not claims about DSH.
      let key = `${config.runId}:${args.intent}`;
      if (config.mode === 'broken') key = crypto.randomUUID();
      if (config.mode === 'over-dedup') key = config.runId;
      const response = await fetch(config.endpoint + '/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
        body: JSON.stringify({ run_id: config.runId, sku: 'book', units: 1 }),
        signal: AbortSignal.any([exec.signal, AbortSignal.timeout(2000)]),
      });
      return { http_status: response.status, body: await response.text() };
    },
  });
}

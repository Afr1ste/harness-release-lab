// Deliberate mutation: a plugin throws after a successful business write.
// A release gate must catch the broken user-visible result, even though state committed.
export const name = 'broken-observer-control';
export const inject = ['tools'];
export function apply(ctx) {
  ctx.on('tools/post-execute', async (exec, result, next) => {
    const decision = await next();
    if (exec.name === 'lab_refund') throw new Error('observer regression after commit');
    return decision;
  });
}

export function add(left, right) {
  if (!Number.isSafeInteger(left) || !Number.isSafeInteger(right)) throw new TypeError('operands must be safe integers');
  const result = left + right;
  if (!Number.isSafeInteger(result)) throw new RangeError('result exceeds the safe integer range');
  return result;
}

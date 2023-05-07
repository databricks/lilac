export function isObject(item: unknown): item is Record<string, unknown> {
  return item && typeof item === 'object' && !Array.isArray(item) ? true : false;
}

export function mergeDeep<T>(target: T, ...sources: T[]): T {
  if (!sources.length) return target;
  const source = sources.shift();

  if (isObject(target) && isObject(source)) {
    for (const key in source) {
      const t = target[key];
      const s = source[key];
      if (isObject(s) && isObject(t)) {
        if (!t) Object.assign(target, { [key]: {} });
        mergeDeep(t, s);
      } else if (!t) {
        Object.assign(target, { [key]: s });
      }
    }
  }
  return mergeDeep(target, ...sources);
}

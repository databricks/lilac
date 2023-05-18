import {test} from 'vitest';
import {isPathVisible} from './datasetViewStore';

test('isPathVisible', () => {
  expect(isPathVisible([['foo', 'bar']], ['foo', 'bar'], {})).toBe(true);
  expect(isPathVisible([], ['foo', 'bar'], {})).toBe(false);
  expect(isPathVisible([['foo', 'bar']], ['foo', 'bar', 'baz'], {})).toBe(false);
  expect(isPathVisible([['alias']], ['foo', 'bar'], {alias: ['foo', 'bar']})).toBe(true);
  expect(isPathVisible([['alias', 'baz']], ['foo', 'bar', 'baz'], {alias: ['foo', 'bar']})).toBe(
    true
  );
});

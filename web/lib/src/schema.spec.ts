import {describe, expect, it} from 'vitest';
import {deserializePath, pathIncludes, pathIsEqual, pathIsMatching, serializePath} from './schema';

describe('schema', () => {
  it('deserialize path', () => {
    expect(deserializePath(['foo', 'bar'])).toEqual(['foo', 'bar']);
    expect(deserializePath('foo.bar')).toEqual(['foo', 'bar']);
    expect(deserializePath('foo.bar.*')).toEqual(['foo', 'bar', '*']);
    expect(deserializePath('foo.bar."something.with.dots".xyz')).toEqual([
      'foo',
      'bar',
      'something.with.dots',
      'xyz'
    ]);
  });

  it('serialize path', () => {
    expect(serializePath(['foo', 'bar'])).toEqual('foo.bar');
    expect(serializePath(['foo', 'bar', '*'])).toEqual('foo.bar.*');
    expect(serializePath(['foo', 'bar', 'something.with.dots', 'xyz'])).toEqual(
      'foo.bar."something.with.dots".xyz'
    );
  });

  it('pathIsEqual', () => {
    expect(pathIsEqual(['foo', 'bar'], ['foo', 'bar'])).toBe(true);
    expect(pathIsEqual(['foo', 'bar'], ['foo', 'bar', 'baz'])).toBe(false);
    expect(pathIsEqual('foo.bar', ['foo', 'bar'])).toBe(true);
  });

  it('pathIncludes', () => {
    expect(pathIncludes(['foo', 'bar'], ['foo', 'bar'])).toBe(true);
    expect(pathIncludes(['foo', 'bar', 'baz'], ['foo', 'bar'])).toBe(true);
    expect(pathIncludes(['foo', 'bar'], ['foo', 'bar', 'baz'])).toBe(false);
    expect(pathIncludes('foo.bar.baz', ['foo', 'bar'])).toBe(true);
  });

  it('pathIsMatching', () => {
    expect(pathIsMatching(['foo', 'bar'], ['foo', 'bar'])).toBe(true);
    expect(pathIsMatching('foo.*.bar', 'foo.1.bar')).toBe(true);
  });
});

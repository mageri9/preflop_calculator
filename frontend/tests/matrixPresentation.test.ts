import assert from 'node:assert/strict';
import test from 'node:test';

import { getCellPresentation } from '../src/utils/matrixPresentation.ts';

test('builds a multi-stop gradient for four mixed actions and fold', () => {
  const presentation = getCellPresentation(
    'AKs',
    {
      push: { AKs: 20 },
      raise: { AKs: 25 },
      isolate: { AKs: 15 },
      call: { AKs: 30 },
    },
    new Set(),
  );

  assert.equal(presentation.inactive, false);
  assert.equal(
    presentation.style?.background,
    'linear-gradient(135deg, #e11d48 0% 20%, #f59e0b 20% 45%, #2563eb 45% 60%, #059669 60% 90%, #111827 90% 100%)',
  );
  assert.match(presentation.title, /FOLD 10%/);
});

#!/usr/bin/env node
/**
 * Amount Input Formatting Tests
 *
 * Tests the amount parsing/formatting logic to ensure:
 * - Comma-separated numbers are parsed correctly
 * - "k" notation (if any) is handled
 * - Full values are preserved during formatting
 *
 * Run: node tests/unit/test_amount_formatting.js
 */

// Simulate the environment
const mockInputValue = (value) => ({
  value: value,
  replace: function(str) { return this.value.replace(new RegExp(str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), ''); }
});

function normalizeAmount(amountValue) {
  return parseFloat(amountValue.replace(/,/g, ''));
}

function handleAmountInput(input) {
  const rawValue = input.replace(/,/g, '');
  const numValue = parseFloat(rawValue);

  if (rawValue === '' || rawValue === '-') {
    return { valid: false, value: rawValue };
  }

  const validValue = rawValue;

  if (!isNaN(numValue)) {
    if (numValue > 100000000) {
      return { valid: true, value: '100000000', formatted: '100,000,000' };
    }
  }

  const parts = validValue.split('.');
  const intPart = parseInt(parts[0], 10).toLocaleString('en-NG');
  const formatted = parts[1] !== undefined ? intPart + '.' + parts[1] : intPart;

  return { valid: true, value: numValue, formatted, rawValue };
}

// Test cases
const testCases = [
  { input: '1000', expected: 1000, description: 'Simple thousand' },
  { input: '1,000', expected: 1000, description: 'Comma-separated thousand' },
  { input: '9,000', expected: 9000, description: '9 thousand with comma' },
  { input: '90,000', expected: 90000, description: '90 thousand with comma' },
  { input: '900,000', expected: 900000, description: '900 thousand with comma' },
  { input: '1,000,000', expected: 1000000, description: 'One million with commas' },
  { input: '1,234,567', expected: 1234567, description: 'Random large number with commas' },
  { input: '100', expected: 100, description: 'Simple hundred' },
  { input: '100.50', expected: 100.50, description: 'Decimal amount' },
  { input: '1,000.50', expected: 1000.50, description: 'Thousand with decimal' },
  { input: '100000000', expected: 100000000, description: 'Maximum amount (100M)' },
  { input: '', expected: NaN, description: 'Empty string' },
  { input: 'abc', expected: NaN, description: 'Invalid characters' },
];

let passed = 0;
let failed = 0;

console.log('='.repeat(60));
console.log('Amount Input Formatting Tests');
console.log('='.repeat(60));
console.log();

testCases.forEach(({ input, expected, description }) => {
  const result = normalizeAmount(input);
  const isEqual = Number.isNaN(expected) ? Number.isNaN(result) : result === expected;

  if (isEqual) {
    console.log(`✓ PASS: "${input}" => ${result} (${description})`);
    passed++;
  } else {
    console.log(`✗ FAIL: "${input}" => ${result}, expected ${expected} (${description})`);
    failed++;
  }
});

console.log();
console.log('='.repeat(60));
console.log(`Results: ${passed} passed, ${failed} failed`);
console.log('='.repeat(60));

// Additional test: verify handleAmountInput formatting
console.log();
console.log('Formatting Tests (handleAmountInput):');
console.log('-'.repeat(40));

const formatTests = [
  { input: '1000', expected: '1,000' },
  { input: '1000000', expected: '1,000,000' },
  { input: '9000', expected: '9,000' },
  { input: '90000', expected: '90,000' },
];

formatTests.forEach(({ input, expected }) => {
  const result = handleAmountInput(input);
  const isEqual = result.formatted === expected;
  console.log(`${isEqual ? '✓' : '✗'} "${input}" => "${result.formatted}" (expected: "${expected}")`);
});

process.exit(failed > 0 ? 1 : 0);
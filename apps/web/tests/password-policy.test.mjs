import assert from "node:assert/strict";
import test from "node:test";

import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  validatePasswordClient,
  validatePasswordConfirmation,
} from "../lib/password-policy.ts";

test("client password policy mirrors the API contract", () => {
  // Too short / empty
  assert.match(validatePasswordClient(""), /至少/);
  assert.match(validatePasswordClient("Ab1"), /至少/);
  assert.equal(validatePasswordClient("a1".repeat(4)), null); // exactly 8, letter+digit

  // Too long (the "A1" prefix already contributes 2 characters)
  const tooLong = `A1${"x".repeat(PASSWORD_MAX_LENGTH - 1)}`;
  assert.equal(tooLong.length, PASSWORD_MAX_LENGTH + 1);
  assert.match(validatePasswordClient(tooLong), /最长/);
  const maxOk = `A1${"x".repeat(PASSWORD_MAX_LENGTH - 2)}`;
  assert.equal(maxOk.length, PASSWORD_MAX_LENGTH);
  assert.equal(validatePasswordClient(maxOk), null);

  // Character classes
  assert.match(validatePasswordClient("abcdefgh"), /字母和数字/);
  assert.match(validatePasswordClient("12345678"), /字母和数字/);
  assert.equal(validatePasswordClient("abcdefg1"), null);

  // Bounds exported for UI copy stay in sync with the server policy
  assert.equal(PASSWORD_MIN_LENGTH, 8);
  assert.equal(PASSWORD_MAX_LENGTH, 64);
});

test("confirmation check reports mismatch after policy passes", () => {
  assert.match(validatePasswordConfirmation("abcdefg1", "abcdefg2"), /不一致/);
  assert.equal(validatePasswordConfirmation("abcdefg1", "abcdefg1"), null);
  // Policy errors take precedence over the mismatch message
  assert.match(validatePasswordConfirmation("short1", "other2"), /至少/);
});

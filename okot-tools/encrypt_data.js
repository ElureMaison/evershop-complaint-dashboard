#!/usr/bin/env node
/*
 * encrypt_data.js — turn data/updates.json into a file that is safe to publish.
 *
 * The digest carries volunteer, student and therapist names alongside real
 * message text, and the page is served from a public GitHub Pages repo. A
 * client-side password check does not protect a JSON file sitting next to the
 * page — anyone can fetch it directly. So the password becomes the decryption
 * key instead of a gate: what gets published is ciphertext.
 *
 * AES-256-GCM, key derived with PBKDF2-HMAC-SHA256. Both sides use standard
 * primitives (node:crypto here, Web Crypto in the browser) — nothing is
 * hand-rolled.
 *
 *   node encrypt_data.js <password> [in] [out]
 */
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const ITERATIONS = 310000;           // OWASP floor for PBKDF2-SHA256
const KEY_BYTES = 32;
const SALT_BYTES = 16;
const IV_BYTES = 12;

const [, , password, inPath, outPath] = process.argv;
if (!password) {
  console.error('usage: node encrypt_data.js <password> [in.json] [out.json]');
  process.exit(1);
}

const src = inPath || path.join(__dirname, 'data', 'updates.json');
const dst = outPath || path.join(__dirname, 'data', 'updates.enc.json');

const plaintext = fs.readFileSync(src);
const salt = crypto.randomBytes(SALT_BYTES);
const iv = crypto.randomBytes(IV_BYTES);
const key = crypto.pbkdf2Sync(password, salt, ITERATIONS, KEY_BYTES, 'sha256');

const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
const tag = cipher.getAuthTag();

const envelope = {
  v: 1,
  kdf: 'PBKDF2-SHA256',
  iterations: ITERATIONS,
  cipher: 'AES-256-GCM',
  salt: salt.toString('base64'),
  iv: iv.toString('base64'),
  // GCM's tag is appended to the ciphertext, which is what Web Crypto expects.
  ct: Buffer.concat([ciphertext, tag]).toString('base64'),
};

fs.writeFileSync(dst, JSON.stringify(envelope));
const ratio = (fs.statSync(dst).size / plaintext.length).toFixed(2);
console.log(`encrypted ${(plaintext.length / 1024).toFixed(0)}KB -> ${dst} (${ratio}x)`);

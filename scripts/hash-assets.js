#!/usr/bin/env node
/**
 * hash-assets.js — content-based filenames for cache busting (Requirement 23.4)
 *
 * Reads static assets (CSS and JS), computes 8-char MD5 hashes of their content,
 * copies them to hashed filenames, and writes a manifest.json mapping original
 * filenames to hashed ones.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const STATIC_DIR = path.join(__dirname, "..", "static");
const CSS_DIR = path.join(STATIC_DIR, "css");
const JS_DIR = path.join(STATIC_DIR, "js");
const MANIFEST = path.join(STATIC_DIR, "manifest.json");

/**
 * Hash a file and copy it to a hashed filename
 * @param {string} srcPath - Source file path
 * @param {string} dir - Directory containing the file
 * @param {string} filename - Original filename
 * @returns {string} - Hashed filename
 */
function hashFile(srcPath, dir, filename) {
  if (!fs.existsSync(srcPath)) {
    console.warn(`WARNING: ${srcPath} not found, skipping.`);
    return filename; // Return original filename if file doesn't exist
  }

  const content = fs.readFileSync(srcPath);
  const hash = crypto.createHash("md5").update(content).digest("hex").slice(0, 8);
  const ext = path.extname(filename);
  const base = path.basename(filename, ext);
  const hashedName = `${base}.${hash}${ext}`;
  const dest = path.join(dir, hashedName);

  fs.copyFileSync(srcPath, dest);
  console.log(`✓ Hashed: ${filename} → ${hashedName}`);
  
  return hashedName;
}

/**
 * Clean up old hashed files (keep only the latest)
 * @param {string} dir - Directory to clean
 * @param {string} pattern - Regex pattern to match hashed files
 * @param {string} keepFile - Filename to keep
 */
function cleanOldHashes(dir, pattern, keepFile) {
  const files = fs.readdirSync(dir);
  const regex = new RegExp(pattern);
  
  files.forEach(file => {
    if (regex.test(file) && file !== keepFile) {
      const filePath = path.join(dir, file);
      fs.unlinkSync(filePath);
      console.log(`✓ Cleaned: ${file}`);
    }
  });
}

// Build manifest
const manifest = {};

// Hash CSS files
console.log("\n📦 Hashing CSS files...");
const cssFile = "output.css";
const cssSrc = path.join(CSS_DIR, cssFile);
const hashedCss = hashFile(cssSrc, CSS_DIR, cssFile);
manifest[`css/${cssFile}`] = `css/${hashedCss}`;
cleanOldHashes(CSS_DIR, /^output\.[a-f0-9]{8}\.css$/, hashedCss);

// Hash JS files
console.log("\n📦 Hashing JS files...");
const jsFiles = ["login.js", "dashboard.js", "verify.js", "loading-states.js"];

jsFiles.forEach(jsFile => {
  const jsSrc = path.join(JS_DIR, jsFile);
  const hashedJs = hashFile(jsSrc, JS_DIR, jsFile);
  manifest[`js/${jsFile}`] = `js/${hashedJs}`;
  
  // Clean old hashed versions
  const base = path.basename(jsFile, ".js");
  cleanOldHashes(JS_DIR, new RegExp(`^${base}\\.[a-f0-9]{8}\\.js$`), hashedJs);
});

// Write manifest
fs.writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2) + "\n");
console.log(`\n✓ Manifest written to: ${MANIFEST}`);
console.log("\n✅ Cache busting complete!\n");

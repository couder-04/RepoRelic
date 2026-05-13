# VS Code Marketplace Deployment Checklist

## ✅ Completed Requirements

- [x] **Extension Name & Display Name** — `reporelic`, `RepoRelic`
- [x] **Version** — `0.0.3`
- [x] **Publisher** — `couder-04`
- [x] **Description** — Clear, concise overview of functionality
- [x] **License** — MIT (in `extension/LICENSE`)
- [x] **Repository URL** — https://github.com/couder-04/RepoRelic
- [x] **VS Code Compatibility** — `^1.85.0`
- [x] **Activation Events** — `onCommand:reporelic.analyze`
- [x] **Icon** — (add `extension/media/icon.png` if desired for marketplace)
- [x] **README.md** — Comprehensive with features, requirements, installation, and configuration
- [x] **CHANGELOG.md** — Version history and recent changes
- [x] **TypeScript Compilation** — `npm run compile` produces `out/*.js`
- [x] **.vscodeignore** — Properly excludes build artifacts, source files
- [x] **package.json** — All required fields populated

## ⚠️ Optional But Recommended

- **Icon**: Add a 128x128 PNG logo at `extension/media/icon.png` and reference in `package.json`:
  ```json
  "icon": "media/icon.png"
  ```
  
- **Keywords**: Add to `package.json`:
  ```json
  "keywords": ["python", "testing", "analysis", "ai", "refactoring"]
  ```

- **Categories**: Current categories `["Testing", "Linters", "Other"]` are appropriate

## 📦 Publishing Steps

### 1. Install VSCE (VS Code Extension manager)
```bash
npm install -g vsce
```

### 2. Create Publisher Account
- Go to https://marketplace.visualstudio.com/
- Sign in or create Microsoft account
- Create a new publisher (or use existing `couder-04`)

### 3. Generate Personal Access Token (PAT)
- In Azure DevOps (https://dev.azure.com)
- Create PAT with **Marketplace (publish)** scope
- Token valid for 90 days (renewable)

### 4. Login to VSCE
```bash
vsce login couder-04
# Paste your PAT when prompted
```

### 5. Package and Publish
```bash
cd extension
vsce publish
# or specific version:
vsce publish 0.0.3
```

### 6. Verify on Marketplace
- Check https://marketplace.visualstudio.com/items?itemName=couder-04.reporelic

## ⚠️ Important Pre-Deployment Notes

1. **Python Engine Distribution**
   - The extension requires users to:
     - Clone/download RepoRelic repo separately
     - Install Python dependencies manually
     - Set `reporelic.repoPath` in VS Code settings
   - This is acceptable for marketplace, as complex runtime dependencies are often user-managed

2. **API Key Security**
   - VS Code automatically treats settings with "ApiKey" or "api" in their name as secrets
   - Verify: Settings > Security > check that API keys are marked as "password" type if needed
   - Users should NOT commit `.env` files to version control

3. **Size Constraints**
   - Compiled extension is small (~50KB), well under the 50MB limit
   - No bundling required (webpack not used for publish)

4. **Update Process**
   - Bump version in `extension/package.json`
   - Update `CHANGELOG.md`
   - Run `vsce publish <new-version>`
   - Creates new GitHub release and marketplace listing automatically (if using VSCE with GitHub integration)

## ⏭️ Post-Deployment

- Monitor marketplace rating and reviews
- Address user feedback and issues via GitHub
- Plan future versions with additional LLM providers or analysis enhancements

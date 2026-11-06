# Publishing S-Lang for Visual Studio Code

1. Create a Visual Studio Marketplace publisher.
2. Replace `REPLACE_WITH_MARKETPLACE_PUBLISHER` in `package.json` with that publisher ID.
3. Ensure the `repository` URL points to the public S-Lang VS Code repository.
4. Run `npm install` and `npm run validate`.
5. Run `npx vsce package` to produce the VSIX.
6. Authenticate the publisher and run `npx vsce publish` or upload the VSIX through Marketplace publisher management.

The extension expects the S-Lang CLI to be installed separately and starts `slang lsp`.

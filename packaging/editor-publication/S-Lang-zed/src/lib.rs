use zed_extension_api as zed;

struct SlangExtension;

impl zed::Extension for SlangExtension {
    fn new() -> Self {
        Self
    }

    fn language_server_command(
        &mut self,
        _language_server_id: &zed::LanguageServerId,
        _worktree: &zed::Worktree,
    ) -> zed::Result<zed::Command> {
        Ok(zed::Command {
            command: "slang".to_string(),
            args: vec!["lsp".to_string()],
            env: vec![],
        })
    }
}

zed::register_extension!(SlangExtension);

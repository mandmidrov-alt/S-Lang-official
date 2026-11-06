local M = {}

function M.setup(opts)
  opts = opts or {}
  if opts.server_path then
    vim.g.slang_server_path = opts.server_path
  end

  require("slang.lsp").setup({
    cmd = { vim.g.slang_server_path or "slang", "lsp" },
    settings = opts.settings,
  })
end

function M.commands()
  local commands = require("slang.commands")

  vim.api.nvim_create_user_command("SlangRun", function()
    commands.run_file(false)
  end, {})

  vim.api.nvim_create_user_command("SlangRunNativeJit", function()
    commands.run_file(true)
  end, {})

  vim.api.nvim_create_user_command("SlangCheck", function()
    commands.check_file()
  end, {})

  vim.api.nvim_create_user_command("SlangRunProject", function()
    commands.run_project(false)
  end, {})

  vim.api.nvim_create_user_command("SlangRunProjectNativeJit", function()
    commands.run_project(true)
  end, {})

  vim.api.nvim_create_user_command("SlangCheckProject", function()
    commands.check_project()
  end, {})

  vim.api.nvim_create_user_command("SlangInit", function()
    commands.init_project()
  end, {})
end

return M

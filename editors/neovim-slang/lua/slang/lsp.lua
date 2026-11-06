local M = {}
local project = require("slang.project")

local defaults = {
  cmd = { "slang", "lsp" },
}

function M.setup(opts)
  opts = vim.tbl_deep_extend("force", defaults, opts or {})

  if vim.lsp.config then
    vim.lsp.config("slang", {
      cmd = opts.cmd,
      filetypes = { "slang" },
      root_markers = { "slang.toml", ".git" },
      settings = opts.settings,
    })
    vim.lsp.enable("slang")
    return
  end

  vim.api.nvim_create_autocmd("FileType", {
    pattern = "slang",
    callback = function(args)
      local root = project.root(vim.api.nvim_buf_get_name(args.buf))
      vim.lsp.start({
        name = "slang",
        cmd = opts.cmd,
        root_dir = root,
        settings = opts.settings,
      }, {
        bufnr = args.buf,
      })
    end,
    group = vim.api.nvim_create_augroup("S_LangLsp", { clear = true }),
  })
end

return M

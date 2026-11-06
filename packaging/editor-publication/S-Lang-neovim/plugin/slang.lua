if vim.g.loaded_slang then
  return
end
vim.g.loaded_slang = true

local slang = require("slang")

slang.setup({})
slang.commands()

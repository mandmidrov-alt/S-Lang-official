local M = {}

local function normalize(path)
  return vim.fs.normalize(path)
end

function M.root(start)
  start = start or vim.api.nvim_buf_get_name(0)
  if start == "" then
    start = vim.loop.cwd()
  end

  local path = normalize(start)
  if vim.fn.filereadable(path) == 1 then
    path = vim.fs.dirname(path)
  end

  local marker = vim.fs.find({ "slang.toml", ".git" }, {
    path = path,
    upward = true,
  })[1]

  if marker then
    if vim.fs.basename(marker) == "slang.toml" then
      return vim.fs.dirname(marker)
    end
    return vim.fs.dirname(marker)
  end

  return vim.fs.dirname(path)
end

function M.manifest(root)
  root = root or M.root()
  local path = root and (root .. "/slang.toml") or nil
  if not path or vim.fn.filereadable(path) ~= 1 then
    return nil
  end
  return path
end

function M.entry(root)
  root = root or M.root()
  local manifest = M.manifest(root)
  if not manifest then
    return nil
  end

  for _, line in ipairs(vim.fn.readfile(manifest)) do
    local value = line:match('^%s*entry%s*=%s*["\']([^"\']+)["\']%s*$')
    if value then
      return value
    end
  end

  return "src/main.sl"
end

return M

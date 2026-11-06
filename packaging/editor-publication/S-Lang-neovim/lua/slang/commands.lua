local M = {}
local project = require("slang.project")

local function terminal(command, cwd)
  vim.cmd("botright new")
  local buf = vim.api.nvim_get_current_buf()
  vim.api.nvim_buf_set_option(buf, "bufhidden", "wipe")
  vim.fn.termopen(command, {
    cwd = cwd,
    on_exit = function(_, code)
      vim.schedule(function()
        if code == 0 then
          vim.notify("S-Lang command completed successfully", vim.log.levels.INFO)
        else
          vim.notify("S-Lang command failed (exit " .. code .. ")", vim.log.levels.ERROR)
        end
      end)
    end,
  })
  vim.cmd("startinsert")
end

local function command()
  return vim.g.slang_server_path or "slang"
end

function M.run_file(native_jit)
  local file = vim.api.nvim_buf_get_name(0)
  if file == "" then
    vim.notify("No S-Lang file is open", vim.log.levels.WARN)
    return
  end

  local args = { command(), "run" }
  if native_jit then
    table.insert(args, "--native-jit")
  end
  table.insert(args, file)
  terminal(args, vim.fs.dirname(file))
end

function M.check_file()
  local file = vim.api.nvim_buf_get_name(0)
  if file == "" then
    vim.notify("No S-Lang file is open", vim.log.levels.WARN)
    return
  end
  terminal({ command(), "check", file }, vim.fs.dirname(file))
end

function M.run_project(native_jit)
  local root = project.root()
  local entry = project.entry(root)
  if not root or not entry then
    vim.notify("No S-Lang project (slang.toml) found", vim.log.levels.WARN)
    return
  end

  local args = { command(), "run" }
  if native_jit then
    table.insert(args, "--native-jit")
  end
  table.insert(args, entry)
  terminal(args, root)
end

function M.check_project()
  local root = project.root()
  local entry = project.entry(root)
  if not root or not entry then
    vim.notify("No S-Lang project (slang.toml) found", vim.log.levels.WARN)
    return
  end
  terminal({ command(), "check", entry }, root)
end

function M.init_project()
  local root = vim.fn.input("S-Lang project directory: ", vim.loop.cwd(), "dir")
  if root == "" then return end
  terminal({ command(), "init", "." }, root)
end

return M

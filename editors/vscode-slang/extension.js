
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let client;
let workspaceWatcher;
let taskProvider;

function serverCommand() {
  return vscode.workspace
    .getConfiguration("slang")
    .get("serverPath", "slang")
    .trim()
    .replace(/^"(.*)"$/, "$1");
}

function isExecutablePath(value) {
  if (!value || typeof value !== "string") return false;
  const unquoted = value.trim().replace(/^"(.*)"$/, "$1");
  // A bare command such as "slang" is not a personalized executable path.
  if (!path.isAbsolute(unquoted)) return false;
  try {
    return fs.statSync(unquoted).isFile();
  } catch {
    return false;
  }
}

function candidateExecutables() {
  const candidates = [];
  const add = (base) => {
    if (!base) return;
    if (process.platform === "win32") {
      candidates.push(path.join(base, "dist", "windows-x86_64", "slang1.0.exe"));
      candidates.push(path.join(base, "dist", "slang1.0.exe"));
      candidates.push(path.join(base, "slang1.0.exe"));
    } else {
      candidates.push(path.join(base, "dist", "slang"));
      candidates.push(path.join(base, "slang"));
    }
  };

  for (const folder of vscode.workspace.workspaceFolders || []) {
    let current = folder.uri.fsPath;
    for (let depth = 0; depth < 5; depth += 1) {
      add(current);
      const parent = path.dirname(current);
      if (parent === current) break;
      current = parent;
    }
  }

  if (process.platform === "win32") {
    const home = process.env.USERPROFILE;
    add("C:\\S-Lang");
    add("C:\\SL");
    add(home && path.join(home, "S-Lang"));
    add(home && path.join(home, "Documents", "S-Lang"));
  }

  return [...new Set(candidates)].filter((candidate) => {
    try { return fs.statSync(candidate).isFile(); } catch { return false; }
  });
}

async function persistDefaultSettings(configuration) {
  const inspected = configuration.inspect("diagnostics.enabled");
  if (inspected && inspected.globalValue === undefined) {
    await configuration.update("diagnostics.enabled", true, vscode.ConfigurationTarget.Global);
  }
  const maxProblems = configuration.inspect("diagnostics.maxProblems");
  if (maxProblems && maxProblems.globalValue === undefined) {
    await configuration.update("diagnostics.maxProblems", 100, vscode.ConfigurationTarget.Global);
  }
  const autoStart = configuration.inspect("project.autoStartLanguageServer");
  if (autoStart && autoStart.globalValue === undefined) {
    await configuration.update("project.autoStartLanguageServer", true, vscode.ConfigurationTarget.Global);
  }
}

async function configureServerPath(forcePicker = false) {
  const configuration = vscode.workspace.getConfiguration("slang");
  await persistDefaultSettings(configuration);

  const current = serverCommand();
  if (!forcePicker && isExecutablePath(current)) return current;

  const candidates = candidateExecutables();
  let selected;

  if (!forcePicker && candidates.length === 1) {
    selected = candidates[0];
  } else if (!forcePicker && candidates.length > 1) {
    const choice = await vscode.window.showQuickPick(
      candidates.map((file) => ({ label: path.basename(path.dirname(path.dirname(path.dirname(file)))), description: file, file })),
      { title: "Select the S-Lang executable", placeHolder: "Found more than one S-Lang executable" }
    );
    selected = choice && choice.file;
  }

  if (!selected) {
    const choice = await vscode.window.showOpenDialog({
      title: "Select the S-Lang executable",
      openLabel: "Use this S-Lang executable",
      canSelectMany: false,
      canSelectFiles: true,
      canSelectFolders: false,
      filters: process.platform === "win32" ? { "S-Lang executable": ["exe"] } : { "S-Lang executable": ["exe", "bin", "out"] }
    });
    selected = choice && choice[0] && choice[0].fsPath;
  }

  if (!selected) {
    if (current && current !== "slang" && !isExecutablePath(current)) {
      vscode.window.showWarningMessage(`S-Lang executable was not found: ${current}. Use “S-Lang: Configure Executable” to select it.`);
    }
    return undefined;
  }

  if (!isExecutablePath(selected)) {
    vscode.window.showErrorMessage(`The selected file does not exist or is not a file: ${selected}`);
    return undefined;
  }

  await configuration.update("serverPath", selected, vscode.ConfigurationTarget.Global);
  vscode.window.showInformationMessage(`S-Lang executable saved to User settings: ${selected}`);
  return selected;
}

function workspaceRootForUri(uri) {
  if (!uri || uri.scheme !== "file") return undefined;

  let current = path.dirname(uri.fsPath);

  while (true) {
    if (fs.existsSync(path.join(current, "slang.toml"))) {
      return current;
    }

    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }

  const folder = vscode.workspace.getWorkspaceFolder(uri);
  return folder ? folder.uri.fsPath : undefined;
}

function projectRoot() {
  const editor = vscode.window.activeTextEditor;
  const fromEditor =
    editor && workspaceRootForUri(editor.document.uri);

  if (fromEditor) return fromEditor;

  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) return undefined;

  return (
    workspaceRootForUri(folders[0].uri) ||
    folders[0].uri.fsPath
  );
}

function projectEntry(root) {
  if (!root) return undefined;

  const manifest = path.join(root, "slang.toml");
  if (!fs.existsSync(manifest)) return undefined;

  const text = fs.readFileSync(manifest, "utf8");
  const match = text.match(/^\s*entry\s*=\s*["']([^"']+)["']\s*$/m);

  return match ? match[1] : "src/main.sl";
}

function currentSlangFile() {
  const editor = vscode.window.activeTextEditor;

  if (!editor || editor.document.languageId !== "slang") {
    vscode.window.showWarningMessage(
      "Open an S-Lang (.sl) file first."
    );
    return null;
  }

  return editor.document.uri.fsPath;
}

/*
 * Quote an argument for PowerShell.
 * Single quotes inside a single-quoted PowerShell string
 * are escaped by doubling them.
 */
function shellQuote(value) {
  const text = String(value);

  if (process.platform === "win32") {
    return "'" + text.replace(/'/g, "''") + "'";
  }

  return "'" + text.replace(/'/g, "'\\''") + "'";
}

/*
 * Format the executable separately from its arguments.
 *
 * PowerShell treats "slang" as a string expression rather
 * than invoking it. Bare executable names must stay unquoted.
 * Executable paths containing spaces are invoked with &.
 */
function shellCommand(value) {
  const command = String(value).trim();

  if (
    process.platform === "win32" &&
    /^[a-zA-Z0-9_.-]+$/.test(command)
  ) {
    return command;
  }

  if (process.platform === "win32") {
    return "& " + shellQuote(command);
  }

  return shellQuote(command);
}

function runInTerminal(args, cwd) {
  const file = currentSlangFile();
  if (!file) return;

  const command = serverCommand();

  const terminal = vscode.window.createTerminal({
    name: "S-Lang",
    cwd: cwd || path.dirname(file)
  });

  terminal.show(true);
  terminal.sendText(
    `${shellCommand(command)} ${args} ${shellQuote(file)}`,
    true
  );
}

function runProjectInTerminal(mode = "run") {
  const root = projectRoot();

  if (!root) {
    vscode.window.showWarningMessage(
      "Open an S-Lang project containing slang.toml."
    );
    return;
  }

  const entry = projectEntry(root);

  if (!entry) {
    vscode.window.showWarningMessage(
      "Could not determine the S-Lang project entry point."
    );
    return;
  }

  const command = serverCommand();
  const terminal = vscode.window.createTerminal({
    name: "S-Lang Project",
    cwd: root
  });

  terminal.show(true);
  terminal.sendText(
    `${shellCommand(command)} ${mode} ${shellQuote(entry)}`,
    true
  );
}

function showProjectInfo() {
  const root = projectRoot();

  if (!root) {
    vscode.window.showWarningMessage(
      "Open an S-Lang project containing slang.toml."
    );
    return;
  }

  const terminal = vscode.window.createTerminal({
    name: "S-Lang Project",
    cwd: root
  });

  terminal.show(true);
  terminal.sendText(
    `${shellCommand(serverCommand())} project .`,
    true
  );
}

function initializeProject() {
  const folders = vscode.workspace.workspaceFolders;
  const defaultUri =
    folders && folders.length ? folders[0].uri : undefined;

  vscode.window.showInputBox({
    prompt: "S-Lang project directory",
    value: defaultUri ? defaultUri.fsPath : "",
    placeHolder: "Path to the project directory"
  }).then((directory) => {
    if (!directory) return;

    const terminal = vscode.window.createTerminal({
      name: "S-Lang Project",
      cwd: directory
    });

    terminal.show(true);
    terminal.sendText(
      `${shellCommand(serverCommand())} init .`,
      true
    );
  });
}

async function startLanguageServer(context) {
  if (client) {
    await client.stop();
    client = undefined;
  }

  const command = serverCommand();
  const root = projectRoot();

  const folders = (vscode.workspace.workspaceFolders || []).map(
    (folder, index) => ({
      uri: folder.uri.toString(),
      name: folder.name,
      index
    })
  );

  const serverOptions = {
    command,
    args: ["lsp"],
    transport: TransportKind.stdio,
    options: {
      cwd: root,
      env: process.env
    }
  };

  const outputChannel = vscode.window.createOutputChannel(
    "S-Lang Language Server"
  );

  const clientOptions = {
    documentSelector: [
      {
        scheme: "file",
        language: "slang"
      }
    ],
    synchronize: {
      configurationSection: "slang"
    },
    workspaceFolder: root
      ? {
          uri: vscode.Uri.file(root).toString(),
          name: path.basename(root),
          index: 0
        }
      : undefined,
    workspaceFolders: folders,
    outputChannel,
    traceOutputChannel: outputChannel
  };

  client = new LanguageClient(
    "slangLanguageServer",
    "S-Lang Language Server",
    serverOptions,
    clientOptions
  );

  client.onDidChangeState((event) => {
    outputChannel.appendLine(
      `Language client state changed: ${event.oldState} -> ${event.newState}`
    );
    // Make unexpected server termination explicit in the dedicated channel.
    // This is diagnostic reporting, not an automatic restart loop.
    if (event.newState === 2) {
      outputChannel.appendLine(
        "S-Lang Language Server stopped. Check the executable path and server process log; exit code 0 can still mean the server received EOF."
      );
    }
  });

  context.subscriptions.push(client);
  context.subscriptions.push(clientOptions.outputChannel);

  try {
    await client.start();
    outputChannel.appendLine(
      `S-Lang language server started using: ${command} lsp`
    );
  } catch (error) {
    outputChannel.appendLine(
      `S-Lang language server startup failed: ${error.stack || error}`
    );
    client = undefined;

    vscode.window.showErrorMessage(
      `S-Lang Language Server could not be started: ${
        error.message || error
      }`
    );

    throw error;
  }
}

async function restartLanguageServer(context) {
  await startLanguageServer(context);
}

class SlangTaskProvider {
  provideTasks() {
    const root = projectRoot();
    const entry = projectEntry(root);

    if (!root || !entry) return [];

    const command = serverCommand();
    const tasks = [];

    const definitions = [
      [
        "Run Project",
        "run",
        "Run the S-Lang project entry point"
      ],
      [
        "Check Project",
        "check",
        "Validate the S-Lang project entry point"
      ],
      [
        "Run Project with Native JIT",
        "run --native-jit",
        "Run the project with the bundled LLVM JIT"
      ]
    ];

    for (const [name, args, detail] of definitions) {
      const task = new vscode.Task(
        {
          type: "slang",
          task: name
        },
        vscode.TaskScope.Workspace,
        `S-Lang: ${name}`,
        "S-Lang",
        new vscode.ShellExecution(
          `${shellCommand(command)} ${args} ${shellQuote(entry)}`,
          {
            cwd: root
          }
        )
      );

      task.detail = detail;
      task.presentationOptions = {
        reveal: vscode.TaskRevealKind.Always,
        panel: vscode.TaskPanelKind.Shared,
        clear: false
      };

      tasks.push(task);
    }

    return tasks;
  }

  resolveTask(task) {
    const root = projectRoot();
    const entry = projectEntry(root);

    if (!root || !entry) return undefined;

    const command = serverCommand();
    const name = task.name;

    let args = "run";

    if (name.includes("Check")) {
      args = "check";
    }

    if (name.includes("Native JIT")) {
      args = "run --native-jit";
    }

    task.execution = new vscode.ShellExecution(
      `${shellCommand(command)} ${args} ${shellQuote(entry)}`,
      {
        cwd: root
      }
    );

    return task;
  }
}

function registerProjectWatcher(context) {
  workspaceWatcher =
    vscode.workspace.createFileSystemWatcher("**/slang.toml");

  const refresh = () => {
    if (taskProvider) {
      vscode.tasks.fetchTasks();
    }
  };

  workspaceWatcher.onDidCreate(
    refresh,
    null,
    context.subscriptions
  );

  workspaceWatcher.onDidChange(
    refresh,
    null,
    context.subscriptions
  );

  workspaceWatcher.onDidDelete(
    refresh,
    null,
    context.subscriptions
  );

  context.subscriptions.push(workspaceWatcher);
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "slang.runFile",
      () => runInTerminal("run", projectRoot())
    ),

    vscode.commands.registerCommand(
      "slang.checkFile",
      () => runInTerminal("check", projectRoot())
    ),

    vscode.commands.registerCommand(
      "slang.runNativeJit",
      () => runInTerminal("run --native-jit", projectRoot())
    ),

    vscode.commands.registerCommand(
      "slang.runProject",
      () => runProjectInTerminal("run")
    ),

    vscode.commands.registerCommand(
      "slang.checkProject",
      () => runProjectInTerminal("check")
    ),

    vscode.commands.registerCommand(
      "slang.runProjectNativeJit",
      () => runProjectInTerminal("run --native-jit")
    ),

    vscode.commands.registerCommand(
      "slang.showProject",
      showProjectInfo
    ),

    vscode.commands.registerCommand(
      "slang.initProject",
      initializeProject
    ),

    vscode.commands.registerCommand(
      "slang.configureServerPath",
      async () => {
        const selected = await configureServerPath(true);
        if (selected) await restartLanguageServer(context);
      }
    ),

    vscode.commands.registerCommand(
      "slang.restartLanguageServer",
      () => restartLanguageServer(context)
    )
  );

  taskProvider = vscode.tasks.registerTaskProvider(
    "slang",
    new SlangTaskProvider()
  );

  context.subscriptions.push(taskProvider);

  registerProjectWatcher(context);

  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(() => {
      restartLanguageServer(context).catch((error) => {
        vscode.window.showErrorMessage(
          `S-Lang Language Server could not be restarted: ${
            error.message || error
          }`
        );
      });
    })
  );

  const autoStart = vscode.workspace
    .getConfiguration("slang")
    .get("project.autoStartLanguageServer", true);

  if (!autoStart) return;

  (async () => {
    const executable = await configureServerPath(false);
    if (!executable) return;
    await startLanguageServer(context);
  })().catch((error) => {
    // startLanguageServer already displays a startup error.
    console.error("S-Lang Language Server startup failed:", error);
  });
}

async function deactivate() {
  if (workspaceWatcher) {
    workspaceWatcher.dispose();
    workspaceWatcher = undefined;
  }

  if (client) {
    await client.stop();
    client = undefined;
  }
}

module.exports = {
  activate,
  deactivate
};

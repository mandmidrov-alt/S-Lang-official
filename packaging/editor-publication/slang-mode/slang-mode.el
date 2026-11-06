;;; slang-mode.el --- Major mode and Eglot integration for S-Lang -*- lexical-binding: t; -*-
;; Version: 1.0.0
;; Package-Requires: ((emacs "29.1"))
;; Keywords: languages, tools
;; URL: https://github.com/mandmidrov-alt/S-Lang-official

;; Copyright (C) 2026 S-Lang contributors
;; SPDX-License-Identifier: MIT

;;; Commentary:
;; A lightweight major mode for S-Lang source files.  Eglot is used as the
;; canonical LSP client; the language server is the S-Lang CLI command
;; `slang lsp'.

;;; Code:

(require 'cl-lib)
(require 'eglot)
(require 'project)

(defgroup slang nil
  "Support for the S-Lang programming language."
  :group 'languages)

(defcustom slang-server-command "slang"
  "Executable used to start the S-Lang language server."
  :type 'string
  :group 'slang)

(defcustom slang-indent-offset 4
  "Indentation width used by `slang-mode'."
  :type 'integer
  :group 'slang)

(defconst slang--keywords
  '("let" "state" "set" "show" "if" "then" "else" "for" "while" "return"
    "function" "record" "entity" "property" "data" "graph" "physics" "body"
    "circle" "simulate" "sequence" "module" "import" "export" "private"
    "from" "as" "in" "where" "map" "sort" "by" "asc" "desc" "reduce"
    "sum" "count" "max" "min" "average" "avg" "any" "all" "tee"
    "choose" "minimizing" "maximizing" "find" "path" "satisfy" "until"
    "steps" "step" "using" "cost" "value" "and" "or" "not" "true" "false" "none"))

(defconst slang--font-lock-keywords
  `((,(regexp-opt slang--keywords 'symbols) . font-lock-keyword-face)
    ("\\_<[A-Za-z_][A-Za-z0-9_]*\\_>[[:space:]]*=" . font-lock-variable-name-face)
    ("\\_<[0-9]+\\(?:\\.[0-9]+\\)?\\_>" . font-lock-constant-face)
    ("\\_<[A-Za-z_][A-Za-z0-9_]*\\_>[[:space:]]*(" . font-lock-function-call-face)))

(defun slang--project-root ()
  "Return the nearest S-Lang project root, or nil."
  (locate-dominating-file default-directory "slang.toml"))

(defun slang--server-command ()
  "Return the Eglot command for S-Lang."
  (list slang-server-command "lsp"))

(defun slang--register-eglot ()
  "Register the S-Lang language server with Eglot."
  (add-to-list 'eglot-server-programs
               `(slang-mode . ,(slang--server-command))))

(defun slang-start-lsp ()
  "Start or connect to the S-Lang language server for the current buffer."
  (interactive)
  (slang--register-eglot)
  (eglot-ensure))

(defun slang-run-file ()
  "Run the current S-Lang source file."
  (interactive)
  (unless buffer-file-name
    (user-error "Current buffer is not visiting a file"))
  (compile (mapconcat #'identity
                      (list slang-server-command "run"
                            (shell-quote-argument buffer-file-name))
                      " ")))

(defun slang-check-file ()
  "Check the current S-Lang source file."
  (interactive)
  (unless buffer-file-name
    (user-error "Current buffer is not visiting a file"))
  (compile (mapconcat #'identity
                      (list slang-server-command "check"
                            (shell-quote-argument buffer-file-name))
                      " ")))

(defun slang-run-native-jit ()
  "Run the current S-Lang source file with native LLVM JIT."
  (interactive)
  (unless buffer-file-name
    (user-error "Current buffer is not visiting a file"))
  (compile (mapconcat #'identity
                      (list slang-server-command "run" "--native-jit"
                            (shell-quote-argument buffer-file-name))
                      " ")))

(defun slang-run-project ()
  "Run the current S-Lang project."
  (interactive)
  (let ((default-directory (or (slang--project-root) default-directory)))
    (compile (concat slang-server-command " run"))))

(defun slang-check-project ()
  "Check the current S-Lang project."
  (interactive)
  (let ((default-directory (or (slang--project-root) default-directory)))
    (compile (concat slang-server-command " check"))))

(defun slang-run-project-native-jit ()
  "Run the current S-Lang project with native LLVM JIT."
  (interactive)
  (let ((default-directory (or (slang--project-root) default-directory)))
    (compile (concat slang-server-command " run --native-jit"))))

(defun slang-init-project ()
  "Initialize an S-Lang project in the current directory."
  (interactive)
  (compile (concat slang-server-command " init")))

(defun slang-show-project-info ()
  "Show S-Lang project information."
  (interactive)
  (let ((default-directory (or (slang--project-root) default-directory)))
    (compile (concat slang-server-command " project"))))

(defun slang-indent-line ()
  "Indent the current S-Lang line using simple block indentation."
  (interactive)
  (let ((indent 0)
        (pos (- (point-max) (point))))
    (save-excursion
      (beginning-of-line)
      (unless (bobp)
        (forward-line -1)
        (setq indent (current-indentation))
        (when (looking-at ".*[:{][[:space:]]*$")
          (setq indent (+ indent slang-indent-offset))))
      (beginning-of-line)
      (when (looking-at "^[[:space:]]*}")
        (setq indent (max 0 (- indent slang-indent-offset))))
      (indent-line-to indent))
    (when (> pos 0) (goto-char (- (point-max) pos)))))

(defvar slang-mode-map
  (let ((map (make-sparse-keymap)))
    (define-key map (kbd "C-c C-l") #'slang-start-lsp)
    (define-key map (kbd "C-c C-r") #'slang-run-file)
    (define-key map (kbd "C-c C-c") #'slang-check-file)
    (define-key map (kbd "C-c C-j") #'slang-run-native-jit)
    (define-key map (kbd "C-c C-p r") #'slang-run-project)
    (define-key map (kbd "C-c C-p c") #'slang-check-project)
    (define-key map (kbd "C-c C-p j") #'slang-run-project-native-jit)
    (define-key map (kbd "C-c C-p i") #'slang-init-project)
    (define-key map (kbd "C-c C-p p") #'slang-show-project-info)
    map))

;;;###autoload
(define-derived-mode slang-mode prog-mode "S-Lang"
  "Major mode for editing S-Lang source files."
  :group 'slang
  (setq-local comment-start "#")
  (setq-local comment-end "")
  (setq-local font-lock-defaults '((slang--font-lock-keywords)))
  (setq-local indent-line-function #'slang-indent-line)
  (setq-local tab-width slang-indent-offset)
  (setq-local indent-tabs-mode nil)
  (when (fboundp 'eglot-ensure)
    (slang--register-eglot)))

;;;###autoload
(add-to-list 'auto-mode-alist '("\\.sl\\'" . slang-mode))

(provide 'slang-mode)
;;; slang-mode.el ends here

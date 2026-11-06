#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include <stdint.h>
#include <limits.h>
#include <math.h>

#if defined(_WIN32)
#define SLANG_API __declspec(dllexport)
#else
#define SLANG_API
#endif

SLANG_API void slang_print_result(double position, double velocity) {
    printf("earth.position = %.15g m\n", position);
    printf("earth.velocity = %.15g mps\n", velocity);
}

/* Stable opaque ABI for native List<Number> values. The list owns its buffer. */
typedef struct { size_t count; double *items; } SlangNumberList;

SLANG_API SlangNumberList *slang_number_list_new(size_t count) {
    SlangNumberList *list = (SlangNumberList *)calloc(1, sizeof(SlangNumberList));
    if (!list) return NULL;
    list->count = count;
    list->items = count ? (double *)calloc(count, sizeof(double)) : NULL;
    if (count && !list->items) { free(list); return NULL; }
    return list;
}

SLANG_API int slang_number_list_append(SlangNumberList *list, double value) {
    if (!list || list->count >= (size_t)LONG_MAX) return 0;
    double *grown = (double *)realloc(list->items, (list->count + 1) * sizeof(double));
    if (!grown) return 0;
    list->items = grown;
    list->items[list->count++] = value;
    return 1;
}

SLANG_API int slang_number_list_set(SlangNumberList *list, size_t index, double value) {
    if (!list || index >= list->count) return 0;
    list->items[index] = value;
    return 1;
}

SLANG_API long slang_number_list_count(const SlangNumberList *list) {
    return list ? (long)list->count : 0;
}

SLANG_API double slang_number_list_item(const SlangNumberList *list, long index) {
    if (!list || index < 0 || (size_t)index >= list->count) return 0.0;
    return list->items[index];
}

SLANG_API void slang_number_list_free(SlangNumberList *list) {
    if (!list) return;
    free(list->items);
    free(list);
}

SLANG_API double slang_reduce_f64(const double *values, long count, double initial, int op) {
    double acc = initial;
    for (long i = 0; i < count; ++i) {
        switch (op) {
            case 0: acc = acc + values[i]; break;
            case 1: acc = acc - values[i]; break;
            case 2: acc = acc * values[i]; break;
            case 3: acc = acc / values[i]; break;
            default: return acc;
        }
    }
    return acc;
}


#include <sys/stat.h>
#include <errno.h>

/* Cross-platform file-type predicates. Windows uses _S_IFMT/_S_IFREG/_S_IFDIR. */
#if defined(_WIN32)
#define SLANG_S_ISREG(mode) (((mode) & _S_IFMT) == _S_IFREG)
#define SLANG_S_ISDIR(mode) (((mode) & _S_IFMT) == _S_IFDIR)
#else
#define SLANG_S_ISREG(mode) S_ISREG(mode)
#define SLANG_S_ISDIR(mode) S_ISDIR(mode)
#endif

SLANG_API int slang_file_exists(const char *path) {
    struct stat st;
    return path != NULL && stat(path, &st) == 0;
}

SLANG_API double slang_file_size(const char *path) {
    struct stat st;
    if (path == NULL || stat(path, &st) != 0) {
        fprintf(stderr, "S-Lang: file_size failed: %s\n", path ? strerror(errno) : "null path");
        exit(1);
    }
    return (double)st.st_size;
}

SLANG_API int slang_is_file(const char *path) {
    struct stat st;
    return path != NULL && stat(path, &st) == 0 && SLANG_S_ISREG(st.st_mode);
}

SLANG_API int slang_is_directory(const char *path) {
    struct stat st;
    return path != NULL && stat(path, &st) == 0 && SLANG_S_ISDIR(st.st_mode);
}

SLANG_API int slang_file_write(const char *path, const char *text) {
    if (path == NULL || text == NULL) return 0;
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    size_t n = strlen(text);
    size_t written = fwrite(text, 1, n, f);
    int ok = (written == n);
    if (fclose(f) != 0) ok = 0;
    return ok;
}


SLANG_API char *slang_file_read(const char *path) {
    if (path == NULL) return NULL;
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "S-Lang: read failed: %s\n", path); exit(1); }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); fprintf(stderr, "S-Lang: read failed: %s\n", path); exit(1); }
    long size = ftell(f);
    if (size < 0) { fclose(f); fprintf(stderr, "S-Lang: read failed: %s\n", path); exit(1); }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); fprintf(stderr, "S-Lang: read failed: %s\n", path); exit(1); }
    char *data = (char *)malloc((size_t)size + 1);
    if (!data) { fclose(f); fprintf(stderr, "S-Lang: read failed: out of memory\n"); exit(1); }
    size_t got = fread(data, 1, (size_t)size, f);
    fclose(f);
    if (got != (size_t)size) { free(data); fprintf(stderr, "S-Lang: read failed: %s\n", path); exit(1); }
    data[size] = '\0';
    return data;
}

static char *slang_strdup(const char *s);

SLANG_API char *slang_text_trim(const char *text) {
    if (!text) return NULL;
    const char *start = text;
    while (*start && isspace((unsigned char)*start)) ++start;
    const char *end = text + strlen(text);
    while (end > start && isspace((unsigned char)end[-1])) --end;
    size_t n = (size_t)(end - start);
    char *out = (char *)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, start, n); out[n] = '\0';
    return out;
}

static char *slang_text_case(const char *text, int upper) {
    if (!text) return NULL;
    size_t n = strlen(text);
    char *out = (char *)malloc(n + 1);
    if (!out) return NULL;
    for (size_t i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)text[i];
        out[i] = (char)(upper ? toupper(c) : tolower(c));
    }
    out[n] = '\0';
    return out;
}

SLANG_API char *slang_text_lower(const char *text) { return slang_text_case(text, 0); }
SLANG_API char *slang_text_upper(const char *text) { return slang_text_case(text, 1); }

SLANG_API int slang_text_starts_with(const char *text, const char *prefix) {
    if (!text || !prefix) return 0;
    size_t n = strlen(prefix);
    return strncmp(text, prefix, n) == 0;
}

SLANG_API int slang_text_ends_with(const char *text, const char *suffix) {
    if (!text || !suffix) return 0;
    size_t n = strlen(text), m = strlen(suffix);
    return m <= n && memcmp(text + n - m, suffix, m) == 0;
}

SLANG_API char *slang_text_replace(const char *text, const char *old_text, const char *new_text) {
    if (!text || !old_text || !new_text) return NULL;
    size_t old_n = strlen(old_text), new_n = strlen(new_text), text_n = strlen(text);
    if (old_n == 0) return slang_strdup(text);
    size_t count = 0;
    const char *p = text;
    while ((p = strstr(p, old_text)) != NULL) { ++count; p += old_n; }
    if (new_n > old_n && count > (SIZE_MAX - text_n - 1) / (new_n - old_n)) return NULL;
    size_t out_n = text_n + count * (new_n - old_n);
    char *out = (char *)malloc(out_n + 1);
    if (!out) return NULL;
    const char *src = text; char *dst = out;
    while ((p = strstr(src, old_text)) != NULL) {
        size_t n = (size_t)(p - src); memcpy(dst, src, n); dst += n;
        memcpy(dst, new_text, new_n); dst += new_n; src = p + old_n;
    }
    strcpy(dst, src);
    return out;
}

SLANG_API void slang_text_free(char *text) { free(text); }

typedef struct { size_t count; char **items; } SlangTextList;
SLANG_API SlangTextList *slang_text_list_new(size_t count);
SLANG_API int slang_text_list_set(SlangTextList *list, size_t index, const char *value);
SLANG_API void slang_text_list_free(SlangTextList *list);

SLANG_API SlangTextList *slang_text_split(const char *text, const char *separator) {
    if (!text || !separator) return NULL;
    size_t sep_n = strlen(separator);
    if (sep_n == 0) {
        SlangTextList *one = slang_text_list_new(1);
        if (!one || !slang_text_list_set(one, 0, text)) { slang_text_list_free(one); return NULL; }
        return one;
    }
    size_t count = 1;
    const char *p = text;
    while ((p = strstr(p, separator)) != NULL) { ++count; p += sep_n; }
    SlangTextList *list = slang_text_list_new(count);
    if (!list) return NULL;
    const char *start = text;
    size_t index = 0;
    while (index < count) {
        const char *hit = strstr(start, separator);
        size_t n = hit ? (size_t)(hit - start) : strlen(start);
        char *part = (char *)malloc(n + 1);
        if (!part) { slang_text_list_free(list); return NULL; }
        memcpy(part, start, n); part[n] = '\0';
        list->items[index++] = part;
        if (!hit) break;
        start = hit + sep_n;
    }
    return list;
}


SLANG_API SlangTextList *slang_file_read_lines(const char *path) {
    char *text = slang_file_read(path);
    if (!text) return NULL;
    size_t capacity = 8, count = 0;
    char **items = (char **)malloc(capacity * sizeof(char *));
    if (!items) { free(text); return NULL; }
    char *start = text;
    for (char *p = text;; ++p) {
        if (*p == '\n' || *p == '\0') {
            if (*p == '\0' && p == start) break;
            if (count == capacity) {
                capacity *= 2;
                char **grown = (char **)realloc(items, capacity * sizeof(char *));
                if (!grown) { for (size_t i=0;i<count;++i) free(items[i]); free(items); free(text); return NULL; }
                items = grown;
            }
            size_t len = (size_t)(p - start);
            if (len && start[len-1] == '\r') --len;
            char *line = (char *)malloc(len + 1);
            if (!line) { for (size_t i=0;i<count;++i) free(items[i]); free(items); free(text); return NULL; }
            memcpy(line, start, len); line[len] = '\0';
            items[count++] = line;
            if (*p == '\0') break;
            start = p + 1;
        }
    }
    free(text);
    SlangTextList *list = (SlangTextList *)malloc(sizeof(SlangTextList));
    if (!list) { for (size_t i=0;i<count;++i) free(items[i]); free(items); return NULL; }
    list->count=count; list->items=items; return list;
}

SLANG_API long slang_text_list_count(const SlangTextList *list) { return list ? (long)list->count : 0; }
SLANG_API const char *slang_text_list_item(const SlangTextList *list, long index) {
    if (!list || index < 0 || (size_t)index >= list->count) return "";
    return list->items[index];
}
SLANG_API void slang_text_list_free(SlangTextList *list) {
    if (!list) return;
    for (size_t i=0;i<list->count;++i) free(list->items[i]);
    free(list->items); free(list);
}

SLANG_API SlangTextList *slang_text_list_new(size_t count) {
    SlangTextList *list = (SlangTextList *)calloc(1, sizeof(SlangTextList));
    if (!list) return NULL;
    list->count = count;
    list->items = count ? (char **)calloc(count, sizeof(char *)) : NULL;
    if (count && !list->items) { free(list); return NULL; }
    return list;
}

SLANG_API int slang_text_list_set(SlangTextList *list, size_t index, const char *value) {
    if (!list || index >= list->count) return 0;
    char *copy = slang_strdup(value ? value : "");
    if (!copy) return 0;
    free(list->items[index]);
    list->items[index] = copy;
    return 1;
}


SLANG_API int slang_file_write_lines(const char *path, const SlangTextList *list) {
    if (path == NULL || list == NULL) return 0;
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    int ok = 1;
    for (size_t i = 0; i < list->count; ++i) {
        const char *line = list->items[i] ? list->items[i] : "";
        size_t n = strlen(line);
        if (fwrite(line, 1, n, f) != n || fputc('\n', f) == EOF) { ok = 0; break; }
    }
    if (fclose(f) != 0) ok = 0;
    return ok;
}



static char *slang_strdup(const char *s) {
    if (!s) return NULL;
    size_t n = strlen(s);
    char *out = (char *)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, s, n + 1);
    return out;
}

SLANG_API char *slang_path_basename(const char *path) {
    if (!path) return NULL;
    const char *end = path + strlen(path);
    while (end > path && (end[-1] == '/' || end[-1] == '\\')) --end;
    const char *p = end;
    while (p > path && p[-1] != '/' && p[-1] != '\\') --p;
    if (p == end) return slang_strdup(".");
    size_t n = (size_t)(end - p);
    char *out = (char *)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, p, n); out[n] = '\0';
    return out;
}

SLANG_API char *slang_path_dirname(const char *path) {
    if (!path || !*path) return slang_strdup(".");
    const char *end = path + strlen(path);
    while (end > path + 1 && (end[-1] == '/' || end[-1] == '\\')) --end;
    const char *p = end;
    while (p > path && p[-1] != '/' && p[-1] != '\\') --p;
    if (p == path) return slang_strdup(".");
    while (p > path + 1 && (p[-1] == '/' || p[-1] == '\\')) --p;
    size_t n = (size_t)(p - path);
    char *out = (char *)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, path, n); out[n] = '\0';
    return out;
}

SLANG_API char *slang_path_extension(const char *path) {
    if (!path) return NULL;
    const char *end = path + strlen(path);
    while (end > path && (end[-1] == '/' || end[-1] == '\\')) --end;
    const char *base = end;
    while (base > path && base[-1] != '/' && base[-1] != '\\') --base;
    const char *dot = end;
    while (dot > base && dot[-1] != '.') --dot;
    if (dot == base || dot == end || dot[-1] != '.') return slang_strdup("");
    return slang_strdup(dot - 1);
}

SLANG_API char *slang_path_join(const char *first, const char *second) {
    if (!first) return slang_strdup(second ? second : "");
    if (!second) return slang_strdup(first);
    size_t a = strlen(first), b = strlen(second);
    int sep = a > 0 && first[a-1] != '/' && first[a-1] != '\\' && b > 0 && second[0] != '/' && second[0] != '\\';
    char *out = (char *)malloc(a + b + (sep ? 1 : 0) + 1);
    if (!out) return NULL;
    memcpy(out, first, a);
    size_t pos = a;
    if (sep) out[pos++] = '/';
    memcpy(out + pos, second, b);
    out[pos+b] = '\0';
    return out;
}

SLANG_API char *slang_path_normalize(const char *path) {
    if (!path) return NULL;
    size_t n = strlen(path);
    char *out = (char *)malloc(n + 1);
    if (!out) return NULL;
    size_t w = 0;
    int last_sep = 0;
    for (size_t i=0; i<n; ++i) {
        char c = path[i] == '\\' ? '/' : path[i];
        if (c == '/') {
            if (!last_sep) out[w++] = c;
            last_sep = 1;
        } else {
            out[w++] = c;
            last_sep = 0;
        }
    }
    while (w > 1 && out[w-1] == '/') --w;
    out[w] = '\0';
    return out;
}


#if defined(_WIN32)
#include <windows.h>
#include <direct.h>
#define SLANG_MKDIR(path) _mkdir(path)
#define SLANG_RMDIR(path) _rmdir(path)
#else
#include <dirent.h>
#include <sys/types.h>
#include <unistd.h>
#define SLANG_MKDIR(path) mkdir((path), 0777)
#define SLANG_RMDIR(path) rmdir(path)
#endif

SLANG_API int slang_make_directory(const char *path) {
    if (path == NULL) return 0;
    return SLANG_MKDIR(path) == 0;
}

SLANG_API int slang_remove_directory(const char *path) {
    if (path == NULL) return 0;
    return SLANG_RMDIR(path) == 0;
}

static int slang_text_compare(const void *a, const void *b) {
    const char *const *left = (const char *const *)a;
    const char *const *right = (const char *const *)b;
    return strcmp(*left, *right);
}

#if defined(_WIN32)
SLANG_API SlangTextList *slang_file_list_directory(const char *path) {
    if (path == NULL) return NULL;
    size_t base_len = strlen(path);
    const char *sep = (base_len > 0 && (path[base_len-1] == '\\' || path[base_len-1] == '/')) ? "" : "\\";
    size_t pattern_len = base_len + strlen(sep) + 2;
    char *pattern = (char *)malloc(pattern_len);
    if (!pattern) return NULL;
    snprintf(pattern, pattern_len, "%s%s*", path, sep);

    WIN32_FIND_DATAA data;
    HANDLE h = FindFirstFileA(pattern, &data);
    free(pattern);
    if (h == INVALID_HANDLE_VALUE) return NULL;

    size_t capacity = 16, count = 0;
    char **items = (char **)malloc(capacity * sizeof(char *));
    if (!items) { FindClose(h); return NULL; }

    do {
        const char *name = data.cFileName;
        if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0) continue;
        if (count == capacity) {
            capacity *= 2;
            char **grown = (char **)realloc(items, capacity * sizeof(char *));
            if (!grown) {
                for (size_t i = 0; i < count; ++i) free(items[i]);
                free(items); FindClose(h); return NULL;
            }
            items = grown;
        }
        items[count] = (char *)malloc(strlen(name) + 1);
        if (!items[count]) {
            for (size_t i = 0; i < count; ++i) free(items[i]);
            free(items); FindClose(h); return NULL;
        }
        strcpy(items[count++], name);
    } while (FindNextFileA(h, &data));
    FindClose(h);

    qsort(items, count, sizeof(char *), slang_text_compare);
    SlangTextList *list = (SlangTextList *)malloc(sizeof(SlangTextList));
    if (!list) {
        for (size_t i = 0; i < count; ++i) free(items[i]);
        free(items); return NULL;
    }
    list->count = count; list->items = items; return list;
}
#else
SLANG_API SlangTextList *slang_file_list_directory(const char *path) {
    if (path == NULL) return NULL;
    DIR *dir = opendir(path);
    if (!dir) return NULL;
    size_t capacity = 16, count = 0;
    char **items = (char **)malloc(capacity * sizeof(char *));
    if (!items) { closedir(dir); return NULL; }

    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        const char *name = entry->d_name;
        if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0) continue;
        if (count == capacity) {
            capacity *= 2;
            char **grown = (char **)realloc(items, capacity * sizeof(char *));
            if (!grown) {
                for (size_t i = 0; i < count; ++i) free(items[i]);
                free(items); closedir(dir); return NULL;
            }
            items = grown;
        }
        items[count] = (char *)malloc(strlen(name) + 1);
        if (!items[count]) {
            for (size_t i = 0; i < count; ++i) free(items[i]);
            free(items); closedir(dir); return NULL;
        }
        strcpy(items[count++], name);
    }
    closedir(dir);
    qsort(items, count, sizeof(char *), slang_text_compare);

    SlangTextList *list = (SlangTextList *)malloc(sizeof(SlangTextList));
    if (!list) {
        for (size_t i = 0; i < count; ++i) free(items[i]);
        free(items); return NULL;
    }
    list->count = count; list->items = items; return list;
}
#endif

/* Process context ------------------------------------------------------- */
SLANG_API SlangTextList *slang_process_arguments(int argc, char **argv) {
    size_t count = argc > 1 ? (size_t)(argc - 1) : 0;
    SlangTextList *list = (SlangTextList *)malloc(sizeof(SlangTextList));
    if (!list) return NULL;
    list->count = count;
    list->items = count ? (char **)calloc(count, sizeof(char *)) : NULL;
    if (count && !list->items) { free(list); return NULL; }
    for (size_t i = 0; i < count; ++i) {
        list->items[i] = slang_strdup(argv[i + 1]);
        if (!list->items[i]) {
            for (size_t j = 0; j < i; ++j) free(list->items[j]);
            free(list->items); free(list); return NULL;
        }
    }
    return list;
}



#if defined(_WIN32)
#include <windows.h>
static char *slang_read_handle(HANDLE h) {
    size_t cap = 4096, len = 0;
    char *buf = (char *)malloc(cap);
    if (!buf) return NULL;
    for (;;) {
        DWORD got = 0;
        if (!ReadFile(h, buf + len, (DWORD)(cap - len - 1), &got, NULL)) break;
        if (!got) break;
        len += (size_t)got;
        if (cap - len < 2) {
            cap *= 2;
            char *grown = (char *)realloc(buf, cap);
            if (!grown) { free(buf); return NULL; }
            buf = grown;
        }
    }
    buf[len] = '\0';
    return buf;
}

SLANG_API SlangTextList *slang_process_run(const char *command) {
    if (!command) return NULL;
    SECURITY_ATTRIBUTES sa = { sizeof(SECURITY_ATTRIBUTES), NULL, TRUE };
    HANDLE out_r = NULL, out_w = NULL, err_r = NULL, err_w = NULL;
    if (!CreatePipe(&out_r, &out_w, &sa, 0) || !CreatePipe(&err_r, &err_w, &sa, 0)) return NULL;
    SetHandleInformation(out_r, HANDLE_FLAG_INHERIT, 0);
    SetHandleInformation(err_r, HANDLE_FLAG_INHERIT, 0);
    char *cmdline = (char *)malloc(strlen(command) + 8);
    if (!cmdline) { CloseHandle(out_r); CloseHandle(out_w); CloseHandle(err_r); CloseHandle(err_w); return NULL; }
    sprintf(cmdline, "cmd.exe /C %s", command);
    STARTUPINFOA si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); ZeroMemory(&pi, sizeof(pi));
    si.cb = sizeof(si); si.dwFlags = STARTF_USESTDHANDLES; si.hStdOutput = out_w; si.hStdError = err_w; si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    BOOL ok = CreateProcessA(NULL, cmdline, NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi);
    free(cmdline); CloseHandle(out_w); CloseHandle(err_w);
    if (!ok) { CloseHandle(out_r); CloseHandle(err_r); return NULL; }
    char *out = slang_read_handle(out_r), *err = slang_read_handle(err_r);
    CloseHandle(out_r); CloseHandle(err_r); WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1; GetExitCodeProcess(pi.hProcess, &code); CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    if (!out || !err) { free(out); free(err); return NULL; }
    char status[32]; snprintf(status, sizeof(status), "%lu", (unsigned long)code);
    SlangTextList *list = (SlangTextList *)malloc(sizeof(SlangTextList));
    if (!list) { free(out); free(err); return NULL; }
    list->count = 3; list->items = (char **)calloc(3, sizeof(char *));
    if (!list->items) { free(list); free(out); free(err); return NULL; }
    list->items[0] = slang_strdup(status); list->items[1] = out; list->items[2] = err;
    if (!list->items[0]) { slang_text_list_free(list); return NULL; }
    return list;
}
#else
#include <sys/wait.h>
#include <sys/select.h>
#include <unistd.h>
SLANG_API SlangTextList *slang_process_run(const char *command) {
    if (!command) return NULL;
    int out_pipe[2], err_pipe[2];
    if (pipe(out_pipe) != 0 || pipe(err_pipe) != 0) return NULL;
    pid_t pid = fork();
    if (pid < 0) return NULL;
    if (pid == 0) {
        dup2(out_pipe[1], STDOUT_FILENO); dup2(err_pipe[1], STDERR_FILENO);
        close(out_pipe[0]); close(out_pipe[1]); close(err_pipe[0]); close(err_pipe[1]);
        execl("/bin/sh", "sh", "-c", command, (char *)NULL);
        _exit(127);
    }
    close(out_pipe[1]); close(err_pipe[1]);
    size_t ocap=4096, olen=0, ecap=4096, elen=0;
    char *out=(char*)malloc(ocap), *err=(char*)malloc(ecap);
    if (!out || !err) { free(out); free(err); close(out_pipe[0]); close(err_pipe[0]); return NULL; }
    int out_open=1, err_open=1;
    while (out_open || err_open) {
        fd_set set; FD_ZERO(&set); int maxfd=-1;
        if (out_open) { FD_SET(out_pipe[0], &set); if (out_pipe[0]>maxfd) maxfd=out_pipe[0]; }
        if (err_open) { FD_SET(err_pipe[0], &set); if (err_pipe[0]>maxfd) maxfd=err_pipe[0]; }
        if (select(maxfd+1, &set, NULL, NULL, NULL) < 0) break;
        if (out_open && FD_ISSET(out_pipe[0], &set)) { char buf[4096]; ssize_t n=read(out_pipe[0],buf,sizeof(buf)); if(n<=0){out_open=0;close(out_pipe[0]);} else {if(olen+(size_t)n+1>ocap){ocap=(olen+(size_t)n+1)*2;out=(char*)realloc(out,ocap);} memcpy(out+olen,buf,(size_t)n);olen+=(size_t)n;} }
        if (err_open && FD_ISSET(err_pipe[0], &set)) { char buf[4096]; ssize_t n=read(err_pipe[0],buf,sizeof(buf)); if(n<=0){err_open=0;close(err_pipe[0]);} else {if(elen+(size_t)n+1>ecap){ecap=(elen+(size_t)n+1)*2;err=(char*)realloc(err,ecap);} memcpy(err+elen,buf,(size_t)n);elen+=(size_t)n;} }
    }
    out[olen]='\0'; err[elen]='\0'; int status=0; waitpid(pid,&status,0);
    int code = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + (WIFSIGNALED(status) ? WTERMSIG(status) : 0);
    char codebuf[32]; snprintf(codebuf,sizeof(codebuf),"%d",code);
    SlangTextList *list=(SlangTextList*)malloc(sizeof(SlangTextList)); if(!list){free(out);free(err);return NULL;}
    list->count=3; list->items=(char**)calloc(3,sizeof(char*)); if(!list->items){free(list);free(out);free(err);return NULL;}
    list->items[0]=slang_strdup(codebuf); list->items[1]=out; list->items[2]=err; return list;
}
#endif
/* Direct process execution. Arguments are passed without a shell. The optional
   cwd is applied only in the child. Environment entries use KEY=VALUE and are
   applied only in the child, preserving the parent's environment otherwise. */
#if defined(_WIN32)
static int slang_append_arg(char **buf, size_t *len, size_t *cap, const char *arg) {
    size_t n = strlen(arg); int quote = (n == 0);
    for (size_t i=0;i<n && !quote;++i) if (arg[i]==' ' || arg[i]=='\t' || arg[i]=='"') quote=1;
    size_t extra = n + (quote ? 2 : 0) + 2;
    if (*len + extra + 1 > *cap) { while (*len + extra + 1 > *cap) *cap *= 2; char *g=(char*)realloc(*buf,*cap); if(!g)return 0; *buf=g; }
    if (*len) (*buf)[(*len)++]=' ';
    if (!quote) { memcpy(*buf+*len,arg,n); *len+=n; }
    else { (*buf)[(*len)++]='"'; for(size_t i=0;i<n;++i){ if(arg[i]=='"') (*buf)[(*len)++]='\\'; (*buf)[(*len)++]=arg[i]; } (*buf)[(*len)++]='"'; }
    (*buf)[*len]='\0'; return 1;
}

SLANG_API SlangTextList *slang_process_run_program(const char *program, const SlangTextList *args, const char *cwd) {
    if (!program || !*program) return NULL;
    SECURITY_ATTRIBUTES sa={sizeof(SECURITY_ATTRIBUTES),NULL,TRUE}; HANDLE out_r=NULL,out_w=NULL,err_r=NULL,err_w=NULL;
    if(!CreatePipe(&out_r,&out_w,&sa,0)||!CreatePipe(&err_r,&err_w,&sa,0)) return NULL;
    SetHandleInformation(out_r,HANDLE_FLAG_INHERIT,0); SetHandleInformation(err_r,HANDLE_FLAG_INHERIT,0);
    size_t cap=256,len=0; char *cmd=(char*)malloc(cap); if(!cmd){CloseHandle(out_r);CloseHandle(out_w);CloseHandle(err_r);CloseHandle(err_w);return NULL;} cmd[0]='\0';
    if(!slang_append_arg(&cmd,&len,&cap,program)){free(cmd);return NULL;}
    if(args) for(size_t i=0;i<args->count;++i) if(!slang_append_arg(&cmd,&len,&cap,args->items[i]?args->items[i]:"")){free(cmd);return NULL;}
    STARTUPINFOA si; PROCESS_INFORMATION pi; ZeroMemory(&si,sizeof(si));ZeroMemory(&pi,sizeof(pi)); si.cb=sizeof(si);si.dwFlags=STARTF_USESTDHANDLES;si.hStdOutput=out_w;si.hStdError=err_w;si.hStdInput=GetStdHandle(STD_INPUT_HANDLE);
    BOOL ok=CreateProcessA(NULL,cmd,NULL,NULL,TRUE,0,NULL,(cwd&&*cwd)?cwd:NULL,&si,&pi); free(cmd); CloseHandle(out_w);CloseHandle(err_w);
    if(!ok){CloseHandle(out_r);CloseHandle(err_r);return NULL;}
    char *out=slang_read_handle(out_r),*err=slang_read_handle(err_r);CloseHandle(out_r);CloseHandle(err_r);WaitForSingleObject(pi.hProcess,INFINITE);DWORD code=1;GetExitCodeProcess(pi.hProcess,&code);CloseHandle(pi.hThread);CloseHandle(pi.hProcess);
    if(!out||!err){free(out);free(err);return NULL;} char status[32];snprintf(status,sizeof(status),"%lu",(unsigned long)code);SlangTextList *list=slang_text_list_new(3);if(!list){free(out);free(err);return NULL;}list->items[0]=slang_strdup(status);list->items[1]=out;list->items[2]=err;if(!list->items[0]){slang_text_list_free(list);return NULL;}return list;
}
#else
SLANG_API SlangTextList *slang_process_run_program(const char *program, const SlangTextList *args, const char *cwd) {
    if(!program||!*program) return NULL; int out_pipe[2],err_pipe[2]; if(pipe(out_pipe)!=0||pipe(err_pipe)!=0)return NULL; pid_t pid=fork(); if(pid<0)return NULL;
    if(pid==0){
        dup2(out_pipe[1],STDOUT_FILENO);dup2(err_pipe[1],STDERR_FILENO);close(out_pipe[0]);close(out_pipe[1]);close(err_pipe[0]);close(err_pipe[1]);
        if(cwd&&*cwd) chdir(cwd);
        size_t argc=1+(args?args->count:0); char **argv=(char**)calloc(argc+1,sizeof(char*)); if(!argv)_exit(126);argv[0]=(char*)program;for(size_t i=0;i<(args?args->count:0);++i)argv[i+1]=args->items[i]?args->items[i]:(char*)"";argv[argc]=NULL;execvp(program,argv);free(argv);_exit(127);
    }
    close(out_pipe[1]);close(err_pipe[1]);size_t ocap=4096,olen=0,ecap=4096,elen=0;char *out=(char*)malloc(ocap),*err=(char*)malloc(ecap);if(!out||!err){free(out);free(err);close(out_pipe[0]);close(err_pipe[0]);return NULL;}int oo=1,eo=1;
    while(oo||eo){fd_set set;FD_ZERO(&set);int maxfd=-1;if(oo){FD_SET(out_pipe[0],&set);if(out_pipe[0]>maxfd)maxfd=out_pipe[0];}if(eo){FD_SET(err_pipe[0],&set);if(err_pipe[0]>maxfd)maxfd=err_pipe[0];}if(select(maxfd+1,&set,NULL,NULL,NULL)<0)break;if(oo&&FD_ISSET(out_pipe[0],&set)){char b[4096];ssize_t n=read(out_pipe[0],b,sizeof(b));if(n<=0){oo=0;close(out_pipe[0]);}else{if(olen+(size_t)n+1>ocap){ocap=(olen+(size_t)n+1)*2;out=(char*)realloc(out,ocap);}memcpy(out+olen,b,(size_t)n);olen+=(size_t)n;}}if(eo&&FD_ISSET(err_pipe[0],&set)){char b[4096];ssize_t n=read(err_pipe[0],b,sizeof(b));if(n<=0){eo=0;close(err_pipe[0]);}else{if(elen+(size_t)n+1>ecap){ecap=(elen+(size_t)n+1)*2;err=(char*)realloc(err,ecap);}memcpy(err+elen,b,(size_t)n);elen+=(size_t)n;}}}
    out[olen]='\0';err[elen]='\0';int status=0;waitpid(pid,&status,0);int code=WIFEXITED(status)?WEXITSTATUS(status):128+(WIFSIGNALED(status)?WTERMSIG(status):0);char codebuf[32];snprintf(codebuf,sizeof(codebuf),"%d",code);SlangTextList *list=slang_text_list_new(3);if(!list){free(out);free(err);return NULL;}list->items[0]=slang_strdup(codebuf);list->items[1]=out;list->items[2]=err;return list;
}
#endif

/* Direct process execution with child-only environment overrides. Entries are
   KEY=VALUE. The parent's environment is never modified. */
#if defined(_WIN32)
static const char *slang_env_key_end(const char *entry) {
    const char *eq = strchr(entry, '=');
    return eq ? eq : entry + strlen(entry);
}
static int slang_env_same_key(const char *a, const char *b) {
    const char *ae = slang_env_key_end(a), *be = slang_env_key_end(b);
    size_t an=(size_t)(ae-a), bn=(size_t)(be-b); if(an!=bn)return 0;
    for(size_t i=0;i<an;++i){ char x=(char)tolower((unsigned char)a[i]), y=(char)tolower((unsigned char)b[i]); if(x!=y)return 0; }
    return 1;
}
static char *slang_build_windows_environment(const SlangTextList *overrides) {
    LPCH base=GetEnvironmentStringsA(); if(!base)return NULL;
    size_t cap=4096,len=0; char *block=(char*)malloc(cap); if(!block){FreeEnvironmentStringsA(base);return NULL;}
    for(const char *p=base;*p;p+=strlen(p)+1){
        int replaced=0; if(overrides) for(size_t i=0;i<overrides->count;++i) if(overrides->items[i]&&slang_env_same_key(p,overrides->items[i])){replaced=1;break;}
        if(replaced)continue;
        size_t n=strlen(p)+1; if(len+n+1>cap){while(len+n+1>cap)cap*=2;char *g=(char*)realloc(block,cap);if(!g){free(block);FreeEnvironmentStringsA(base);return NULL;}block=g;}
        memcpy(block+len,p,n);len+=n;
    }
    if(overrides) for(size_t i=0;i<overrides->count;++i) if(overrides->items[i]&&strchr(overrides->items[i],'=')){
        size_t n=strlen(overrides->items[i])+1; if(len+n+1>cap){while(len+n+1>cap)cap*=2;char *g=(char*)realloc(block,cap);if(!g){free(block);FreeEnvironmentStringsA(base);return NULL;}block=g;}
        memcpy(block+len,overrides->items[i],n);len+=n;
    }
    block[len]='\0'; FreeEnvironmentStringsA(base); return block;
}
SLANG_API SlangTextList *slang_process_run_program_env(const char *program, const SlangTextList *args, const char *cwd, const SlangTextList *overrides) {
    if(!program||!*program)return NULL;
    SECURITY_ATTRIBUTES sa={sizeof(SECURITY_ATTRIBUTES),NULL,TRUE}; HANDLE out_r=NULL,out_w=NULL,err_r=NULL,err_w=NULL;
    if(!CreatePipe(&out_r,&out_w,&sa,0)||!CreatePipe(&err_r,&err_w,&sa,0))return NULL;
    SetHandleInformation(out_r,HANDLE_FLAG_INHERIT,0);SetHandleInformation(err_r,HANDLE_FLAG_INHERIT,0);
    size_t cap=256,len=0;char *cmd=(char*)malloc(cap);if(!cmd){CloseHandle(out_r);CloseHandle(out_w);CloseHandle(err_r);CloseHandle(err_w);return NULL;}cmd[0]='\0';
    if(!slang_append_arg(&cmd,&len,&cap,program)){free(cmd);return NULL;} if(args)for(size_t i=0;i<args->count;++i)if(!slang_append_arg(&cmd,&len,&cap,args->items[i]?args->items[i]:"")){free(cmd);return NULL;}
    char *env_block=slang_build_windows_environment(overrides);if(!env_block){free(cmd);return NULL;}
    STARTUPINFOA si;PROCESS_INFORMATION pi;ZeroMemory(&si,sizeof(si));ZeroMemory(&pi,sizeof(pi));si.cb=sizeof(si);si.dwFlags=STARTF_USESTDHANDLES;si.hStdOutput=out_w;si.hStdError=err_w;si.hStdInput=GetStdHandle(STD_INPUT_HANDLE);
    BOOL ok=CreateProcessA(NULL,cmd,NULL,NULL,TRUE,0,env_block,(cwd&&*cwd)?cwd:NULL,&si,&pi);free(cmd);free(env_block);CloseHandle(out_w);CloseHandle(err_w);if(!ok){CloseHandle(out_r);CloseHandle(err_r);return NULL;}
    char *out=slang_read_handle(out_r),*err=slang_read_handle(err_r);CloseHandle(out_r);CloseHandle(err_r);WaitForSingleObject(pi.hProcess,INFINITE);DWORD code=1;GetExitCodeProcess(pi.hProcess,&code);CloseHandle(pi.hThread);CloseHandle(pi.hProcess);if(!out||!err){free(out);free(err);return NULL;}
    char status[32];snprintf(status,sizeof(status),"%lu",(unsigned long)code);SlangTextList *list=slang_text_list_new(3);if(!list){free(out);free(err);return NULL;}list->items[0]=slang_strdup(status);list->items[1]=out;list->items[2]=err;if(!list->items[0]){slang_text_list_free(list);return NULL;}return list;
}
#else
extern char **environ;
static int slang_env_same_key_posix(const char *a, const char *b) {
    const char *ae=strchr(a,'='),*be=strchr(b,'='); if(!ae||!be)return 0;size_t an=(size_t)(ae-a),bn=(size_t)(be-b);return an==bn&&strncmp(a,b,an)==0;
}
static const char *slang_env_lookup(const SlangTextList *overrides,const char *key) {
    if(overrides)for(size_t i=0;i<overrides->count;++i)if(overrides->items[i]&&slang_env_same_key_posix(overrides->items[i],key))return strchr(overrides->items[i],'=')+1;
    const char *v=getenv(key);return v;
}
static char **slang_build_posix_environment(const SlangTextList *overrides) {
    size_t base=0;while(environ&&environ[base])++base;size_t n=base+(overrides?overrides->count:0)+1;char **envp=(char**)calloc(n,sizeof(char*));if(!envp)return NULL;size_t out=0;
    for(size_t i=0;i<base;++i){int replaced=0;if(overrides)for(size_t j=0;j<overrides->count;++j)if(overrides->items[j]&&slang_env_same_key_posix(environ[i],overrides->items[j])){replaced=1;break;}if(!replaced)envp[out++]=environ[i];}
    if(overrides)for(size_t i=0;i<overrides->count;++i)if(overrides->items[i]&&strchr(overrides->items[i],'='))envp[out++]=overrides->items[i];
    envp[out]=NULL;return envp;
}
static void slang_exec_env(const char *program,char *const argv[],char *const envp[]) {
    if(strchr(program,'/')){execve(program,argv,envp);return;}
    const char *path=NULL;for(char *const *e=envp;*e;++e)if(strncmp(*e,"PATH=",5)==0){path=*e+5;break;}if(!path)path="/usr/local/bin:/usr/bin:/bin";
    const char *start=path;while(1){const char *end=strchr(start,':');size_t dn=end?(size_t)(end-start):strlen(start);size_t pn=dn+1+strlen(program)+1;char *candidate=(char*)malloc(pn);if(!candidate)return;if(dn){memcpy(candidate,start,dn);candidate[dn]='/';strcpy(candidate+dn+1,program);}else strcpy(candidate,program);execve(candidate,argv,envp);free(candidate);if(!end)break;start=end+1;}
}
SLANG_API SlangTextList *slang_process_run_program_env(const char *program, const SlangTextList *args, const char *cwd, const SlangTextList *overrides) {
    if(!program||!*program)return NULL;int out_pipe[2],err_pipe[2];if(pipe(out_pipe)!=0||pipe(err_pipe)!=0)return NULL;pid_t pid=fork();if(pid<0)return NULL;
    if(pid==0){dup2(out_pipe[1],STDOUT_FILENO);dup2(err_pipe[1],STDERR_FILENO);close(out_pipe[0]);close(out_pipe[1]);close(err_pipe[0]);close(err_pipe[1]);if(cwd&&*cwd)chdir(cwd);size_t argc=1+(args?args->count:0);char **argv=(char**)calloc(argc+1,sizeof(char*));if(!argv)_exit(126);argv[0]=(char*)program;for(size_t i=0;i<(args?args->count:0);++i)argv[i+1]=args->items[i]?args->items[i]:(char*)"";argv[argc]=NULL;char **envp=slang_build_posix_environment(overrides);if(!envp)_exit(126);slang_exec_env(program,argv,envp);free(envp);free(argv);_exit(127);}
    close(out_pipe[1]);close(err_pipe[1]);size_t ocap=4096,olen=0,ecap=4096,elen=0;char *out=(char*)malloc(ocap),*err=(char*)malloc(ecap);if(!out||!err){free(out);free(err);close(out_pipe[0]);close(err_pipe[0]);return NULL;}int oo=1,eo=1;
    while(oo||eo){fd_set set;FD_ZERO(&set);int maxfd=-1;if(oo){FD_SET(out_pipe[0],&set);if(out_pipe[0]>maxfd)maxfd=out_pipe[0];}if(eo){FD_SET(err_pipe[0],&set);if(err_pipe[0]>maxfd)maxfd=err_pipe[0];}if(select(maxfd+1,&set,NULL,NULL,NULL)<0)break;if(oo&&FD_ISSET(out_pipe[0],&set)){char b[4096];ssize_t n=read(out_pipe[0],b,sizeof(b));if(n<=0){oo=0;close(out_pipe[0]);}else{if(olen+(size_t)n+1>ocap){ocap=(olen+(size_t)n+1)*2;out=(char*)realloc(out,ocap);}memcpy(out+olen,b,(size_t)n);olen+=(size_t)n;}}if(eo&&FD_ISSET(err_pipe[0],&set)){char b[4096];ssize_t n=read(err_pipe[0],b,sizeof(b));if(n<=0){eo=0;close(err_pipe[0]);}else{if(elen+(size_t)n+1>ecap){ecap=(elen+(size_t)n+1)*2;err=(char*)realloc(err,ecap);}memcpy(err+elen,b,(size_t)n);elen+=(size_t)n;}}}
    out[olen]='\0';err[elen]='\0';int status=0;waitpid(pid,&status,0);int code=WIFEXITED(status)?WEXITSTATUS(status):128+(WIFSIGNALED(status)?WTERMSIG(status):0);char codebuf[32];snprintf(codebuf,sizeof(codebuf),"%d",code);SlangTextList *list=slang_text_list_new(3);if(!list){free(out);free(err);return NULL;}list->items[0]=slang_strdup(codebuf);list->items[1]=out;list->items[2]=err;return list;
}
#endif

SLANG_API char *slang_process_environment(const char *name) {
    if (!name) return slang_strdup("");
    const char *value = getenv(name);
    return slang_strdup(value ? value : "");
}

/*
 * Concrete numeric collection ABI (1.10.23).
 *
 * The MLIR semantic ABI still uses opaque i64 handles.  These entry points
 * make such handles executable for the first concrete collection subset:
 * numeric f64 collections, predicate filtering, scalar mapping, stable
 * ascending sort, reduction and aggregate statistics.  Handles are owned by
 * the runtime and remain valid until slang_collection_free().
 */
typedef struct SlangF64Collection {
    size_t count;
    size_t capacity;
    double *values;
} SlangF64Collection;

static SlangF64Collection *slang_f64_collection_ptr(int64_t handle) {
    return (SlangF64Collection *)(uintptr_t)handle;
}

SLANG_API int64_t slang_collection_f64_new(const double *values, long count) {
    if (count < 0) return 0;
    SlangF64Collection *c = (SlangF64Collection *)calloc(1, sizeof(*c));
    if (!c) return 0;
    c->count = (size_t)count;
    c->capacity = c->count ? c->count : 1;
    c->values = (double *)malloc(c->capacity * sizeof(double));
    if (!c->values) { free(c); return 0; }
    if (count > 0 && values) memcpy(c->values, values, (size_t)count * sizeof(double));
    else if (count > 0) { free(c->values); free(c); return 0; }
    return (int64_t)(uintptr_t)c;
}

SLANG_API int64_t slang_collection_f64_from_scalar(double value) {
    return slang_collection_f64_new(&value, 1);
}

SLANG_API long slang_collection_f64_count(int64_t handle) {
    SlangF64Collection *c = slang_f64_collection_ptr(handle);
    return c ? (long)c->count : 0;
}

SLANG_API double slang_collection_f64_get(int64_t handle, long index) {
    SlangF64Collection *c = slang_f64_collection_ptr(handle);
    if (!c || index < 0 || (size_t)index >= c->count) return 0.0;
    return c->values[index];
}

SLANG_API void slang_collection_free(int64_t handle) {
    SlangF64Collection *c = slang_f64_collection_ptr(handle);
    if (!c) return;
    free(c->values);
    free(c);
}

static int slang_collection_reserve(SlangF64Collection *c, size_t need) {
    if (!c) return 0;
    if (need <= c->capacity) return 1;
    size_t cap = c->capacity ? c->capacity : 1;
    while (cap < need) {
        if (cap > SIZE_MAX / 2) return 0;
        cap *= 2;
    }
    double *grown = (double *)realloc(c->values, cap * sizeof(double));
    if (!grown) return 0;
    c->values = grown;
    c->capacity = cap;
    return 1;
}


/*
 * Concrete numeric record-column ABI (1.10.41).
 *
 * A record collection is represented column-wise.  All fields in this ABI
 * are Number/f64; the semantic schema remains responsible for Text/Boolean
 * and mixed-schema lowering.  filter/map preserve every column and therefore
 * make record handles composable across lowered stages.
 */
typedef struct SlangRecordF64Collection {
    size_t rows;
    size_t fields;
    double **columns;
} SlangRecordF64Collection;

static SlangRecordF64Collection *slang_record_f64_ptr(int64_t handle) {
    return (SlangRecordF64Collection *)(uintptr_t)handle;
}

SLANG_API int64_t slang_record_f64_new(const double *const *columns, long fields, long rows) {
    if (fields < 0 || rows < 0) return 0;
    SlangRecordF64Collection *r = (SlangRecordF64Collection *)calloc(1, sizeof(*r));
    if (!r) return 0;
    r->fields = (size_t)fields;
    r->rows = (size_t)rows;
    r->columns = r->fields ? (double **)calloc(r->fields, sizeof(double *)) : NULL;
    if (r->fields && !r->columns) { free(r); return 0; }
    for (size_t f = 0; f < r->fields; ++f) {
        r->columns[f] = r->rows ? (double *)malloc(r->rows * sizeof(double)) : NULL;
        if (r->rows && !r->columns[f]) {
            for (size_t j = 0; j < f; ++j) free(r->columns[j]);
            free(r->columns); free(r); return 0;
        }
        if (r->rows) {
            if (!columns || !columns[f]) {
                for (size_t j = 0; j <= f; ++j) free(r->columns[j]);
                free(r->columns); free(r); return 0;
            }
            memcpy(r->columns[f], columns[f], r->rows * sizeof(double));
        }
    }
    return (int64_t)(uintptr_t)r;
}

SLANG_API int64_t slang_record_f64_new_flat(const double *flat, long fields, long rows) {
    if (fields < 0 || rows < 0) return 0;
    if ((fields > 0 && rows > 0) && !flat) return 0;
    SlangRecordF64Collection *r = (SlangRecordF64Collection *)calloc(1, sizeof(*r));
    if (!r) return 0;
    r->fields = (size_t)fields;
    r->rows = (size_t)rows;
    r->columns = r->fields ? (double **)calloc(r->fields, sizeof(double *)) : NULL;
    if (r->fields && !r->columns) { free(r); return 0; }
    for (size_t f = 0; f < r->fields; ++f) {
        r->columns[f] = r->rows ? (double *)malloc(r->rows * sizeof(double)) : NULL;
        if (r->rows && !r->columns[f]) { for (size_t j = 0; j < f; ++j) free(r->columns[j]); free(r->columns); free(r); return 0; }
        for (size_t row = 0; row < r->rows; ++row) {
            r->columns[f][row] = flat[row * r->fields + f];
        }
    }
    return (int64_t)(uintptr_t)r;
}

/* 1.10.80: explicit shared-endpoint ABI. The selected global plan owns the
 * lifetime of the endpoint handle; downstream branches reuse the same handle
 * instead of requesting another physical Record copy. */
SLANG_API int64_t slang_record_f64_share(int64_t handle) {
    return slang_record_f64_ptr(handle) ? handle : 0;
}

SLANG_API int64_t slang_record_f64_materialize(int64_t handle) {
    SlangRecordF64Collection *src = slang_record_f64_ptr(handle);
    if (!src) return 0;
    SlangRecordF64Collection *out = (SlangRecordF64Collection*)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->rows = src->rows; out->fields = src->fields;
    out->columns = out->fields ? (double**)calloc(out->fields, sizeof(double*)) : NULL;
    if (out->fields && !out->columns) { free(out); return 0; }
    for (size_t f=0; f<out->fields; ++f) {
        out->columns[f] = out->rows ? (double*)malloc(out->rows * sizeof(double)) : NULL;
        if (out->rows && !out->columns[f]) { for (size_t j=0;j<f;++j) free(out->columns[j]); free(out->columns); free(out); return 0; }
        if (out->rows) memcpy(out->columns[f], src->columns[f], out->rows * sizeof(double));
    }
    return (int64_t)(uintptr_t)out;
}

SLANG_API long slang_record_f64_count(int64_t handle) {
    SlangRecordF64Collection *r = slang_record_f64_ptr(handle);
    return r ? (long)r->rows : 0;
}

SLANG_API long slang_record_f64_field_count(int64_t handle) {
    SlangRecordF64Collection *r = slang_record_f64_ptr(handle);
    return r ? (long)r->fields : 0;
}

SLANG_API double slang_record_f64_get(int64_t handle, long field, long row) {
    SlangRecordF64Collection *r = slang_record_f64_ptr(handle);
    if (!r || field < 0 || row < 0 || (size_t)field >= r->fields || (size_t)row >= r->rows) return 0.0;
    return r->columns[field][row];
}

SLANG_API void slang_record_f64_free(int64_t handle) {
    SlangRecordF64Collection *r = slang_record_f64_ptr(handle);
    if (!r) return;
    for (size_t f = 0; f < r->fields; ++f) free(r->columns[f]);
    free(r->columns);
    free(r);
}

SLANG_API int64_t slang_record_f64_filter(int64_t handle, long field, double threshold, int op) {
    SlangRecordF64Collection *src = slang_record_f64_ptr(handle);
    if (!src || field < 0 || (size_t)field >= src->fields) return 0;
    size_t kept = 0;
    for (size_t i = 0; i < src->rows; ++i) {
        double v = src->columns[field][i];
        int keep = 0;
        switch (op) {
            case 0: keep = v > threshold; break;
            case 1: keep = v >= threshold; break;
            case 2: keep = v < threshold; break;
            case 3: keep = v <= threshold; break;
            case 4: keep = v == threshold; break;
            case 5: keep = v != threshold; break;
            default: return 0;
        }
        if (keep) ++kept;
    }
    SlangRecordF64Collection *out = (SlangRecordF64Collection *)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->rows = kept; out->fields = src->fields;
    out->columns = out->fields ? (double **)calloc(out->fields, sizeof(double *)) : NULL;
    if (out->fields && !out->columns) { free(out); return 0; }
    for (size_t f = 0; f < out->fields; ++f) {
        out->columns[f] = kept ? (double *)malloc(kept * sizeof(double)) : NULL;
        if (kept && !out->columns[f]) { slang_record_f64_free((int64_t)(uintptr_t)out); return 0; }
    }
    size_t dst = 0;
    for (size_t i = 0; i < src->rows; ++i) {
        double v = src->columns[field][i];
        int keep = 0;
        switch (op) {
            case 0: keep = v > threshold; break;
            case 1: keep = v >= threshold; break;
            case 2: keep = v < threshold; break;
            case 3: keep = v <= threshold; break;
            case 4: keep = v == threshold; break;
            case 5: keep = v != threshold; break;
        }
        if (keep) {
            for (size_t f = 0; f < out->fields; ++f) out->columns[f][dst] = src->columns[f][i];
            ++dst;
        }
    }
    return (int64_t)(uintptr_t)out;
}


SLANG_API int64_t slang_record_f64_filter_field_compare(int64_t handle, long left_field, long right_field, double multiplier, int op) {
    SlangRecordF64Collection *src = slang_record_f64_ptr(handle);
    if (!src || left_field < 0 || right_field < 0 || (size_t)left_field >= src->fields || (size_t)right_field >= src->fields) return 0;
    size_t kept = 0;
    for (size_t i = 0; i < src->rows; ++i) {
        double a = src->columns[left_field][i];
        double b = src->columns[right_field][i] * multiplier;
        int keep = 0;
        switch (op) {
            case 0: keep = a > b; break;
            case 1: keep = a >= b; break;
            case 2: keep = a < b; break;
            case 3: keep = a <= b; break;
            case 4: keep = a == b; break;
            case 5: keep = a != b; break;
            default: return 0;
        }
        if (keep) ++kept;
    }
    SlangRecordF64Collection *out = (SlangRecordF64Collection *)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->rows = kept; out->fields = src->fields;
    out->columns = out->fields ? (double **)calloc(out->fields, sizeof(double *)) : NULL;
    if (out->fields && !out->columns) { free(out); return 0; }
    for (size_t f = 0; f < out->fields; ++f) {
        out->columns[f] = kept ? (double *)malloc(kept * sizeof(double)) : NULL;
        if (kept && !out->columns[f]) { slang_record_f64_free((int64_t)(uintptr_t)out); return 0; }
    }
    size_t dst = 0;
    for (size_t i = 0; i < src->rows; ++i) {
        double a = src->columns[left_field][i];
        double b = src->columns[right_field][i] * multiplier;
        int keep = 0;
        switch (op) {
            case 0: keep = a > b; break; case 1: keep = a >= b; break;
            case 2: keep = a < b; break; case 3: keep = a <= b; break;
            case 4: keep = a == b; break; case 5: keep = a != b; break;
        }
        if (keep) { for (size_t f = 0; f < out->fields; ++f) out->columns[f][dst] = src->columns[f][i]; ++dst; }
    }
    return (int64_t)(uintptr_t)out;
}



static double slang_bits_f64(int64_t bits) {
    uint64_t u = (uint64_t)bits;
    double d;
    memcpy(&d, &u, sizeof(d));
    return d;
}

static int slang_record_compare(double a, double b, int op) {
    switch (op) {
        case 0: return a > b; case 1: return a >= b; case 2: return a < b;
        case 3: return a <= b; case 4: return a == b; case 5: return a != b;
        default: return 0;
    }
}

SLANG_API int64_t slang_record_f64_filter_expr(int64_t handle, const int64_t *program, long instructions) {
    SlangRecordF64Collection *src = slang_record_f64_ptr(handle);
    if (!src || !program || instructions <= 0) return 0;
    size_t kept = 0;
    for (size_t row = 0; row < src->rows; ++row) {
        int stack[256]; int sp = 0; int valid = 1;
        for (long pc = 0; pc < instructions; ++pc) {
            const int64_t *ins = program + pc * 5;
            int op = (int)ins[0];
            if (op == 0) { if (sp >= 256) { valid=0; break; } stack[sp++] = ins[1] != 0; }
            else if (op == 1) {
                if (sp >= 256 || ins[1] < 0 || (size_t)ins[1] >= src->fields) { valid=0; break; }
                stack[sp++] = slang_record_compare(src->columns[ins[1]][row], slang_bits_f64(ins[4]), (int)ins[3]);
            } else if (op == 2) {
                if (sp >= 256 || ins[1] < 0 || ins[2] < 0 || (size_t)ins[1] >= src->fields || (size_t)ins[2] >= src->fields) { valid=0; break; }
                double rhs = src->columns[ins[2]][row] * slang_bits_f64(ins[4]);
                stack[sp++] = slang_record_compare(src->columns[ins[1]][row], rhs, (int)ins[3]);
            } else if (op == 3 || op == 4) {
                if (sp < 2) { valid=0; break; }
                int b=stack[--sp], a=stack[--sp]; stack[sp++] = op == 3 ? (a && b) : (a || b);
            } else if (op == 5) {
                if (sp < 1) { valid=0; break; } stack[sp-1] = !stack[sp-1];
            } else { valid=0; break; }
        }
        if (valid && sp == 1 && stack[0]) ++kept;
    }
    SlangRecordF64Collection *out = (SlangRecordF64Collection *)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->rows = kept; out->fields = src->fields;
    out->columns = out->fields ? (double **)calloc(out->fields, sizeof(double *)) : NULL;
    if (out->fields && !out->columns) { free(out); return 0; }
    for (size_t f=0; f<out->fields; ++f) { out->columns[f] = kept ? (double*)malloc(kept*sizeof(double)) : NULL; if (kept && !out->columns[f]) { slang_record_f64_free((int64_t)(uintptr_t)out); return 0; } }
    size_t dst=0;
    for (size_t row=0; row<src->rows; ++row) {
        int stack[256]; int sp=0; int valid=1;
        for (long pc=0; pc<instructions; ++pc) {
            const int64_t *ins=program+pc*5; int op=(int)ins[0];
            if (op==0) stack[sp++]=ins[1]!=0;
            else if (op==1) stack[sp++]=slang_record_compare(src->columns[ins[1]][row], slang_bits_f64(ins[4]), (int)ins[3]);
            else if (op==2) stack[sp++]=slang_record_compare(src->columns[ins[1]][row], src->columns[ins[2]][row]*slang_bits_f64(ins[4]), (int)ins[3]);
            else if (op==3 || op==4) { if(sp<2){valid=0;break;} int b=stack[--sp],a=stack[--sp];stack[sp++]=(op==3)?(a&&b):(a||b); }
            else if (op==5) { if(sp<1){valid=0;break;} stack[sp-1]=!stack[sp-1]; }
            else { valid=0; break; }
        }
        if(valid && sp==1 && stack[0]) { for(size_t f=0;f<out->fields;++f) out->columns[f][dst]=src->columns[f][row]; ++dst; }
    }
    return (int64_t)(uintptr_t)out;
}


/* 1.10.73: schema-preserving numeric Record field mask used by partial
 * recomputation. Unselected columns are zeroed while column positions remain
 * unchanged, matching the mixed Record mask ABI. */
SLANG_API int64_t slang_record_f64_mask_fields(int64_t handle, const int64_t *selected, long field_count) {
    SlangRecordF64Collection *src = slang_record_f64_ptr(handle);
    if (!src || field_count < 0 || (field_count && !selected)) return 0;
    SlangRecordF64Collection *out = (SlangRecordF64Collection *)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->rows = src->rows; out->fields = src->fields;
    out->columns = out->fields ? (double **)calloc(out->fields, sizeof(double *)) : NULL;
    if (out->fields && !out->columns) { free(out); return 0; }
    for (long i=0; i<field_count; ++i) {
        if (selected[i] < 0 || (size_t)selected[i] >= src->fields) { slang_record_f64_free((int64_t)(uintptr_t)out); return 0; }
    }
    for (size_t f=0; f<out->fields; ++f) {
        out->columns[f] = out->rows ? (double *)calloc(out->rows, sizeof(double)) : NULL;
        if (out->rows && !out->columns[f]) { slang_record_f64_free((int64_t)(uintptr_t)out); return 0; }
        int keep=0;
        for (long i=0; i<field_count; ++i) if ((size_t)selected[i] == f) { keep=1; break; }
        if (keep && out->rows) memcpy(out->columns[f], src->columns[f], out->rows * sizeof(double));
    }
    return (int64_t)(uintptr_t)out;
}

/* Execute one postfix program that may update several output fields. Opcode 20
 * stores the top stack value into the selected field. The source collection is
 * copied first, so unchanged fields and row alignment are preserved. */
SLANG_API int64_t slang_record_f64_map_fields_expr(int64_t handle, const int64_t *program, long instructions) {
    SlangRecordF64Collection *src = slang_record_f64_ptr(handle);
    if (!src || !program || instructions <= 0) return 0;
    int64_t out_handle = slang_record_f64_new((const double *const *)src->columns, (long)src->fields, (long)src->rows);
    SlangRecordF64Collection *out = slang_record_f64_ptr(out_handle);
    if (!out) return 0;
    for (size_t row=0; row<out->rows; ++row) {
        double stack[256]; int sp=0; int valid=1;
        for (long pc=0; pc<instructions; ++pc) {
            const int64_t *ins=program+pc*5; int op=(int)ins[0];
            if (op==1) {
                if (sp>=256 || ins[1]<0 || (size_t)ins[1]>=src->fields) { valid=0; break; }
                stack[sp++]=src->columns[ins[1]][row];
            } else if (op==2) {
                if (sp>=256) { valid=0; break; }
                stack[sp++]=slang_bits_f64(ins[4]);
            } else if (op>=3 && op<=7) {
                if (sp<2) { valid=0; break; }
                double b=stack[--sp], a=stack[--sp];
                switch(op) { case 3: stack[sp++]=a+b; break; case 4: stack[sp++]=a-b; break;
                    case 5: stack[sp++]=a*b; break; case 6: stack[sp++]=a/b; break; case 7: stack[sp++]=pow(a,b); break; }
            } else if (op>=10 && op<=15) {
                if (sp<2) { valid=0; break; }
                double b=stack[--sp], a=stack[--sp]; stack[sp++]=(double)slang_record_compare(a,b,op-10);
            } else if (op==16 || op==17) {
                if (sp<2) { valid=0; break; }
                double b=stack[--sp], a=stack[--sp]; stack[sp++]=(op==16)?((a!=0)&&(b!=0)):((a!=0)||(b!=0));
            } else if (op==18) {
                if (sp<1) { valid=0; break; } stack[sp-1]=(stack[sp-1]==0);
            } else if (op==8) {
                if (sp<3) { valid=0; break; }
                double e=stack[--sp], t=stack[--sp], c=stack[--sp]; stack[sp++]=(c!=0)?t:e;
            } else if (op==20) {
                if (sp<1 || ins[1]<0 || (size_t)ins[1]>=out->fields) { valid=0; break; }
                out->columns[ins[1]][row]=stack[--sp];
            } else { valid=0; break; }
        }
        if (!valid || sp != 0) { slang_record_f64_free(out_handle); return 0; }
    }
    return out_handle;
}

SLANG_API int64_t slang_record_f64_map_field_expr(int64_t handle, long target_field, const int64_t *program, long instructions) {
    SlangRecordF64Collection *src = slang_record_f64_ptr(handle);
    if (!src || target_field < 0 || (size_t)target_field >= src->fields || !program || instructions <= 0) return 0;
    int64_t out_handle = slang_record_f64_new((const double *const *)src->columns, (long)src->fields, (long)src->rows);
    SlangRecordF64Collection *out = slang_record_f64_ptr(out_handle); if (!out) return 0;
    for (size_t row=0; row<out->rows; ++row) {
        double stack[256]; int sp=0; int valid=1;
        for(long pc=0;pc<instructions;++pc){
            const int64_t *ins=program+pc*5; int op=(int)ins[0];
            if(op==1){if(sp>=256||ins[1]<0||(size_t)ins[1]>=src->fields){valid=0;break;}stack[sp++]=src->columns[ins[1]][row];}
            else if(op==2){if(sp>=256){valid=0;break;}stack[sp++]=slang_bits_f64(ins[4]);}
            else if(op>=3&&op<=7){if(sp<2){valid=0;break;}double b=stack[--sp],a=stack[--sp];switch(op){case 3:stack[sp++]=a+b;break;case 4:stack[sp++]=a-b;break;case 5:stack[sp++]=a*b;break;case 6:stack[sp++]=a/b;break;case 7:stack[sp++]=pow(a,b);break;}}
            else if(op>=10&&op<=15){if(sp<2){valid=0;break;}double b=stack[--sp],a=stack[--sp];stack[sp++]=(double)slang_record_compare(a,b,op-10);}
            else if(op==16||op==17){if(sp<2){valid=0;break;}double b=stack[--sp],a=stack[--sp];stack[sp++]=(op==16)?((a!=0)&&(b!=0)):((a!=0)||(b!=0));}
            else if(op==18){if(sp<1){valid=0;break;}stack[sp-1]=(stack[sp-1]==0);}
            else if(op==8){if(sp<3){valid=0;break;}double e=stack[--sp],t=stack[--sp],c=stack[--sp];stack[sp++]=(c!=0)?t:e;}
            else {valid=0;break;}
        }
        if(valid&&sp==1) out->columns[target_field][row]=stack[0]; else {slang_record_f64_free(out_handle);return 0;}
    }
    return out_handle;
}

SLANG_API int64_t slang_record_f64_map_field_binary(int64_t handle, long target_field, long other_field, int op) {
    SlangRecordF64Collection *src = slang_record_f64_ptr(handle);
    if (!src || target_field < 0 || other_field < 0 || (size_t)target_field >= src->fields || (size_t)other_field >= src->fields) return 0;
    int64_t out_handle = slang_record_f64_new((const double *const *)src->columns, (long)src->fields, (long)src->rows);
    SlangRecordF64Collection *out = slang_record_f64_ptr(out_handle);
    if (!out) return 0;
    for (size_t i = 0; i < out->rows; ++i) {
        double a = out->columns[target_field][i], b = out->columns[other_field][i];
        switch (op) {
            case 0: out->columns[target_field][i] = a + b; break;
            case 1: out->columns[target_field][i] = a - b; break;
            case 2: out->columns[target_field][i] = a * b; break;
            case 3: out->columns[target_field][i] = a / b; break;
            default: slang_record_f64_free(out_handle); return 0;
        }
    }
    return out_handle;
}

SLANG_API int64_t slang_record_f64_map_field(int64_t handle, long field, double operand, int op) {
    SlangRecordF64Collection *src = slang_record_f64_ptr(handle);
    if (!src || field < 0 || (size_t)field >= src->fields) return 0;
    int64_t out_handle = slang_record_f64_new((const double *const *)src->columns, (long)src->fields, (long)src->rows);
    SlangRecordF64Collection *out = slang_record_f64_ptr(out_handle);
    if (!out) return 0;
    for (size_t i = 0; i < out->rows; ++i) {
        double v = out->columns[field][i];
        switch (op) {
            case 0: out->columns[field][i] = v * operand; break;
            case 1: out->columns[field][i] = v + operand; break;
            case 2: out->columns[field][i] = v - operand; break;
            case 3: out->columns[field][i] = v / operand; break;
            case 4: out->columns[field][i] = pow(v, operand); break;
            default: slang_record_f64_free(out_handle); return 0;
        }
    }
    return out_handle;
}


/* predicate op 0: value > threshold; 1: >=; 2: <; 3: <=; 4: ==; 5: != */
SLANG_API int64_t slang_collection_f64_filter(int64_t handle, double threshold, int op) {
    SlangF64Collection *src = slang_f64_collection_ptr(handle);
    if (!src) return 0;
    SlangF64Collection *out = (SlangF64Collection *)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->capacity = src->count ? src->count : 1;
    out->values = (double *)malloc(out->capacity * sizeof(double));
    if (!out->values) { free(out); return 0; }
    for (size_t i = 0; i < src->count; ++i) {
        double v = src->values[i];
        int keep = 0;
        switch (op) {
            case 0: keep = v > threshold; break;
            case 1: keep = v >= threshold; break;
            case 2: keep = v < threshold; break;
            case 3: keep = v <= threshold; break;
            case 4: keep = v == threshold; break;
            case 5: keep = v != threshold; break;
            default: free(out->values); free(out); return 0;
        }
        if (keep) out->values[out->count++] = v;
    }
    return (int64_t)(uintptr_t)out;
}

/* map op 0: multiply, 1: add, 2: subtract, 3: divide, 4: power */
SLANG_API int64_t slang_collection_f64_map(int64_t handle, double operand, int op) {
    SlangF64Collection *src = slang_f64_collection_ptr(handle);
    if (!src) return 0;
    SlangF64Collection *out = (SlangF64Collection *)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->count = src->count;
    out->capacity = src->count ? src->count : 1;
    out->values = (double *)malloc(out->capacity * sizeof(double));
    if (!out->values) { free(out); return 0; }
    for (size_t i = 0; i < src->count; ++i) {
        switch (op) {
            case 0: out->values[i] = src->values[i] * operand; break;
            case 1: out->values[i] = src->values[i] + operand; break;
            case 2: out->values[i] = src->values[i] - operand; break;
            case 3: out->values[i] = src->values[i] / operand; break;
            case 4: out->values[i] = pow(src->values[i], operand); break;
            default: free(out->values); free(out); return 0;
        }
    }
    return (int64_t)(uintptr_t)out;
}

SLANG_API int64_t slang_collection_f64_sort(int64_t handle) {
    SlangF64Collection *src = slang_f64_collection_ptr(handle);
    if (!src) return 0;
    SlangF64Collection *out = (SlangF64Collection *)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->count = src->count;
    out->capacity = src->count ? src->count : 1;
    out->values = (double *)malloc(out->capacity * sizeof(double));
    if (!out->values) { free(out); return 0; }
    if (src->count) memcpy(out->values, src->values, src->count * sizeof(double));
    for (size_t i = 1; i < out->count; ++i) {
        double x = out->values[i];
        size_t j = i;
        while (j > 0 && out->values[j - 1] > x) {
            out->values[j] = out->values[j - 1];
            --j;
        }
        out->values[j] = x;
    }
    return (int64_t)(uintptr_t)out;
}


static double slang_bits_f64(int64_t bits);
static int slang_record_compare(double a, double b, int op);

/*
 * Mixed record ABI (1.10.46).
 * Field type tags: 0=Number, 1=Boolean, 2=Text.
 * Values are row-major i64 slots: Number uses IEEE-754 bits, Boolean uses 0/1,
 * Text uses a pointer into a caller-owned temporary. The constructor deep-copies
 * text, so the resulting record owns all of its strings.
 */
typedef struct SlangRecordMixedCollection {
    size_t rows;
    size_t fields;
    int *types;
    uint64_t *values;
    char **texts;
} SlangRecordMixedCollection;

static SlangRecordMixedCollection *slang_record_mixed_ptr(int64_t handle) {
    return (SlangRecordMixedCollection *)(uintptr_t)handle;
}

static void slang_record_mixed_release(SlangRecordMixedCollection *r) {
    if (!r) return;
    if (r->texts) {
        size_t total = r->rows * r->fields;
        for (size_t i = 0; i < total; ++i) free(r->texts[i]);
    }
    free(r->texts); free(r->values); free(r->types); free(r);
}

SLANG_API int64_t slang_record_mixed_new_flat(const int64_t *types, const int64_t *values,
                                    const int64_t *text_ptrs, long fields, long rows) {
    if (fields < 0 || rows < 0 || (fields && !types) || (fields && rows && !values)) return 0;
    SlangRecordMixedCollection *r = (SlangRecordMixedCollection *)calloc(1, sizeof(*r));
    if (!r) return 0;
    r->fields=(size_t)fields; r->rows=(size_t)rows;
    r->types = r->fields ? (int *)calloc(r->fields, sizeof(int)) : NULL;
    size_t total=r->fields*r->rows;
    r->values = total ? (uint64_t *)calloc(total, sizeof(uint64_t)) : NULL;
    r->texts = total ? (char **)calloc(total, sizeof(char *)) : NULL;
    if ((r->fields && !r->types) || (total && (!r->values || !r->texts))) { slang_record_mixed_release(r); return 0; }
    for (size_t f=0; f<r->fields; ++f) {
        if (types[f] < 0 || types[f] > 2) { slang_record_mixed_release(r); return 0; }
        r->types[f]=(int)types[f];
    }
    for (size_t i=0; i<total; ++i) {
        r->values[i]=(uint64_t)values[i];
        if (r->types[i % r->fields] == 2) {
            const char *src = text_ptrs ? (const char *)(uintptr_t)text_ptrs[i] : NULL;
            if (!src) { slang_record_mixed_release(r); return 0; }
            size_t n=strlen(src)+1;
            r->texts[i]=(char *)malloc(n);
            if (!r->texts[i]) { slang_record_mixed_release(r); return 0; }
            memcpy(r->texts[i],src,n);
        }
    }
    return (int64_t)(uintptr_t)r;
}

/* 1.10.80: shared mixed Record endpoint; no second physical copy. */
SLANG_API int64_t slang_record_mixed_share(int64_t handle) {
    return slang_record_mixed_ptr(handle) ? handle : 0;
}

SLANG_API int64_t slang_record_mixed_materialize(int64_t handle) {
    SlangRecordMixedCollection *src = slang_record_mixed_ptr(handle);
    if (!src) return 0;
    size_t total = src->rows * src->fields;
    SlangRecordMixedCollection *out = (SlangRecordMixedCollection*)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->rows = src->rows; out->fields = src->fields;
    if (out->fields) out->types = (int*)malloc(out->fields * sizeof(int));
    if (total) { out->values = (uint64_t*)calloc(total, sizeof(uint64_t)); out->texts = (char**)calloc(total, sizeof(char*)); }
    if ((out->fields && !out->types) || (total && (!out->values || !out->texts))) { slang_record_mixed_release(out); return 0; }
    if (out->fields) memcpy(out->types, src->types, out->fields * sizeof(int));
    for (size_t i=0;i<total;++i) {
        out->values[i] = src->values[i];
        if (src->types[i % src->fields] == 2) {
            const char *text = src->texts[i] ? src->texts[i] : "";
            size_t n = strlen(text) + 1;
            out->texts[i] = (char*)malloc(n);
            if (!out->texts[i]) { slang_record_mixed_release(out); return 0; }
            memcpy(out->texts[i], text, n);
        }
    }
    return (int64_t)(intptr_t)out;
}

SLANG_API long slang_record_mixed_count(int64_t handle) {
    SlangRecordMixedCollection *r=slang_record_mixed_ptr(handle); return r ? (long)r->rows : 0;
}
SLANG_API long slang_record_mixed_field_count(int64_t handle) {
    SlangRecordMixedCollection *r=slang_record_mixed_ptr(handle); return r ? (long)r->fields : 0;
}
SLANG_API int slang_record_mixed_field_type(int64_t handle, long field) {
    SlangRecordMixedCollection *r=slang_record_mixed_ptr(handle);
    if (!r || field<0 || (size_t)field>=r->fields) return -1; return r->types[field];
}
SLANG_API double slang_record_mixed_get_number(int64_t handle,long field,long row) {
    SlangRecordMixedCollection *r=slang_record_mixed_ptr(handle);
    if (!r||field<0||row<0||(size_t)field>=r->fields||(size_t)row>=r->rows||r->types[field]!=0) return 0.0;
    return slang_bits_f64((int64_t)r->values[(size_t)row*r->fields+(size_t)field]);
}
SLANG_API int slang_record_mixed_get_bool(int64_t handle,long field,long row) {
    SlangRecordMixedCollection *r=slang_record_mixed_ptr(handle);
    if (!r||field<0||row<0||(size_t)field>=r->fields||(size_t)row>=r->rows||r->types[field]!=1) return 0;
    return r->values[(size_t)row*r->fields+(size_t)field] ? 1 : 0;
}
SLANG_API const char *slang_record_mixed_get_text(int64_t handle,long field,long row) {
    SlangRecordMixedCollection *r=slang_record_mixed_ptr(handle);
    if (!r||field<0||row<0||(size_t)field>=r->fields||(size_t)row>=r->rows||r->types[field]!=2) return NULL;
    return r->texts[(size_t)row*r->fields+(size_t)field];
}
SLANG_API void slang_record_mixed_free(int64_t handle) { slang_record_mixed_release(slang_record_mixed_ptr(handle)); }

/* 1.10.50: schema-driven mixed Record projection/reordering.
 * source_fields selects source columns; target_types is the authoritative
 * output schema contract. No value coercion is performed. */
SLANG_API int64_t slang_record_mixed_project_fields(int64_t handle,
                                          const int64_t *source_fields,
                                          const int64_t *target_types,
                                          long target_fields) {
    SlangRecordMixedCollection *src = slang_record_mixed_ptr(handle);
    if (!src || target_fields < 0 || (target_fields && (!source_fields || !target_types))) return 0;
    SlangRecordMixedCollection *out = (SlangRecordMixedCollection *)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->rows = src->rows;
    out->fields = (size_t)target_fields;
    out->types = out->fields ? (int *)calloc(out->fields, sizeof(int)) : NULL;
    size_t total = out->rows * out->fields;
    out->values = total ? (uint64_t *)calloc(total, sizeof(uint64_t)) : NULL;
    out->texts = total ? (char **)calloc(total, sizeof(char *)) : NULL;
    if ((out->fields && !out->types) || (total && (!out->values || !out->texts))) {
        slang_record_mixed_release(out); return 0;
    }
    for (size_t f = 0; f < out->fields; ++f) {
        long sf = source_fields[f];
        long tt = target_types[f];
        if (sf < 0 || (size_t)sf >= src->fields || tt < 0 || tt > 2 || src->types[sf] != tt) {
            slang_record_mixed_release(out); return 0;
        }
        out->types[f] = (int)tt;
    }
    for (size_t row = 0; row < out->rows; ++row) {
        for (size_t f = 0; f < out->fields; ++f) {
            size_t si = row * src->fields + (size_t)source_fields[f];
            size_t di = row * out->fields + f;
            out->values[di] = src->values[si];
            if (out->types[f] == 2) {
                const char *text = src->texts[si] ? src->texts[si] : "";
                size_t n = strlen(text) + 1;
                out->texts[di] = (char *)malloc(n);
                if (!out->texts[di]) { slang_record_mixed_release(out); return 0; }
                memcpy(out->texts[di], text, n);
            }
        }
    }
    return (int64_t)(uintptr_t)out;
}


/* 1.10.71: schema-preserving field mask used by the selected field-level
 * Record plan. Unlike project_fields, this keeps original column indices so
 * existing downstream operators can continue to use their semantic field
 * positions. Unselected fields are replaced with neutral values. */
SLANG_API int64_t slang_record_mixed_mask_fields(int64_t handle,
                                       const int64_t *selected,
                                       long field_count) {
    SlangRecordMixedCollection *src = slang_record_mixed_ptr(handle);
    if (!src || field_count < 0 || (field_count && !selected)) return 0;
    SlangRecordMixedCollection *out = (SlangRecordMixedCollection *)calloc(1, sizeof(*out));
    if (!out) return 0;
    out->rows = src->rows;
    out->fields = src->fields;
    out->types = out->fields ? (int *)calloc(out->fields, sizeof(int)) : NULL;
    size_t total = out->rows * out->fields;
    out->values = total ? (uint64_t *)calloc(total, sizeof(uint64_t)) : NULL;
    out->texts = total ? (char **)calloc(total, sizeof(char *)) : NULL;
    if ((out->fields && !out->types) || (total && (!out->values || !out->texts))) {
        slang_record_mixed_release(out); return 0;
    }
    for (size_t f = 0; f < out->fields; ++f) out->types[f] = src->types[f];
    for (long i = 0; i < field_count; ++i) {
        if (selected[i] < 0 || (size_t)selected[i] >= src->fields) {
            slang_record_mixed_release(out); return 0;
        }
    }
    for (size_t row = 0; row < out->rows; ++row) {
        for (size_t f = 0; f < out->fields; ++f) {
            int keep = 0;
            for (long i = 0; i < field_count; ++i) {
                if ((size_t)selected[i] == f) { keep = 1; break; }
            }
            size_t idx = row * out->fields + f;
            if (!keep) {
                out->values[idx] = 0;
                if (out->types[f] == 2) {
                    out->texts[idx] = (char *)malloc(1);
                    if (!out->texts[idx]) { slang_record_mixed_release(out); return 0; }
                    out->texts[idx][0] = '\0';
                }
                continue;
            }
            out->values[idx] = src->values[idx];
            if (out->types[f] == 2) {
                const char *text = src->texts[idx] ? src->texts[idx] : "";
                size_t n = strlen(text) + 1;
                out->texts[idx] = (char *)malloc(n);
                if (!out->texts[idx]) { slang_record_mixed_release(out); return 0; }
                memcpy(out->texts[idx], text, n);
            }
        }
    }
    return (int64_t)(uintptr_t)out;
}

static int slang_record_mixed_compare_num(double a,double b,int op) { return slang_record_compare(a,b,op); }
static int slang_record_mixed_compare_text(const char *a,const char *b,int op) {
    int c=strcmp(a?a:"",b?b:"");
    if(op==4) return c==0; if(op==5) return c!=0; return 0;
}

typedef struct SlangMixedValue { int type; double num; int boolean; const char *text; } SlangMixedValue;
static int slang_mixed_push(SlangMixedValue *s,int *sp,int type,double num,int boolean,const char *text) {
    if (*sp>=256) return 0; s[*sp]=(SlangMixedValue){type,num,boolean,text}; ++*sp; return 1;
}

static int slang_record_mixed_eval(const SlangRecordMixedCollection *src,size_t row,
                                   const int64_t *program,long instructions,const char *const *text_pool,long text_count,
                                   SlangMixedValue *stack,int *sp,SlangMixedValue *result) {
    *sp=0;
    for(long pc=0;pc<instructions;++pc) {
        const int64_t *ins=program+pc*5; int op=(int)ins[0];
        if(op==0) { if(!slang_mixed_push(stack,sp,1,0,ins[1]!=0,NULL)) return 0; }
        else if(op==1) { if(!slang_mixed_push(stack,sp,0,slang_bits_f64(ins[4]),0,NULL)) return 0; }
        else if(op==3) {
            long f=ins[1]; int t=(int)ins[2];
            if(f<0||(size_t)f>=src->fields||src->types[f]!=t) return 0;
            size_t idx=row*src->fields+(size_t)f;
            if(t==0) { if(!slang_mixed_push(stack,sp,0,slang_bits_f64((int64_t)src->values[idx]),0,NULL)) return 0; }
            else if(t==1) { if(!slang_mixed_push(stack,sp,1,0,src->values[idx]!=0,NULL)) return 0; }
            else { if(!slang_mixed_push(stack,sp,2,0,0,src->texts[idx])) return 0; }
        } else if(op==23) {
            long ti=ins[1]; if(ti<0||ti>=text_count||!text_pool||!slang_mixed_push(stack,sp,2,0,0,text_pool[ti])) return 0;
        } else if(op>=4&&op<=8) {
            if(*sp<2||stack[*sp-1].type!=0||stack[*sp-2].type!=0) return 0;
            double b=stack[--*sp].num,a=stack[--*sp].num,v=0;
            if(op==4)v=a+b; else if(op==5)v=a-b; else if(op==6)v=a*b; else if(op==7)v=a/b; else v=pow(a,b);
            if(!slang_mixed_push(stack,sp,0,v,0,NULL)) return 0;
        } else if(op>=10&&op<=15) {
            if(*sp<2||stack[*sp-1].type!=0||stack[*sp-2].type!=0) return 0;
            double b=stack[--*sp].num,a=stack[--*sp].num;
            if(!slang_mixed_push(stack,sp,1,0,slang_record_mixed_compare_num(a,b,op-10),NULL)) return 0;
        } else if(op==21||op==22) {
            if(*sp<2||stack[*sp-1].type!=2||stack[*sp-2].type!=2) return 0;
            const char *b=stack[*sp-1].text,*a=stack[*sp-2].text; int v=slang_record_mixed_compare_text(a,b,op==21?4:5); *sp-=2;
            if(!slang_mixed_push(stack,sp,1,0,v,NULL)) return 0;
        } else if(op==24||op==25) {
            if(*sp<2||stack[*sp-1].type!=1||stack[*sp-2].type!=1) return 0;
            int b=stack[--*sp].boolean,a=stack[--*sp].boolean;
            if(!slang_mixed_push(stack,sp,1,0,op==24?(a==b):(a!=b),NULL)) return 0;
        } else if(op==16||op==17) {
            if(*sp<2||stack[*sp-1].type!=1||stack[*sp-2].type!=1) return 0;
            int b=stack[--*sp].boolean,a=stack[--*sp].boolean;
            if(!slang_mixed_push(stack,sp,1,0,op==16?(a&&b):(a||b),NULL)) return 0;
        } else if(op==18) {
            if(*sp<1||stack[*sp-1].type!=1) return 0; stack[*sp-1].boolean=!stack[*sp-1].boolean;
        } else if(op==19) {
            if(*sp<3||stack[*sp-3].type!=1) return 0;
            SlangMixedValue e=stack[--*sp],t=stack[--*sp],c=stack[--*sp];
            if(t.type!=e.type) return 0; stack[(*sp)++]=c.boolean?t:e;
        } else return 0;
    }
    if(*sp!=1) return 0; *result=stack[0]; return 1;
}

SLANG_API int64_t slang_record_mixed_filter_expr(int64_t handle,const int64_t *program,long instructions,const char *const *text_pool,long text_count) {
    SlangRecordMixedCollection *src=slang_record_mixed_ptr(handle);
    if(!src||!program||instructions<=0) return 0;
    size_t kept=0; SlangMixedValue stack[256],res; int sp;
    for(size_t row=0;row<src->rows;++row) { if(!slang_record_mixed_eval(src,row,program,instructions,text_pool,text_count,stack,&sp,&res)||res.type!=1) return 0; if(res.boolean) ++kept; }
    SlangRecordMixedCollection *out=(SlangRecordMixedCollection*)calloc(1,sizeof(*out));
    if(!out) return 0; out->rows=kept; out->fields=src->fields;
    out->types=out->fields?(int*)calloc(out->fields,sizeof(int)):NULL;
    size_t out_total=out->rows*out->fields;
    out->values=out_total?(uint64_t*)calloc(out_total,sizeof(uint64_t)):NULL;
    out->texts=out_total?(char**)calloc(out_total,sizeof(char*)):NULL;
    if((out->fields&&!out->types)||(out_total&&(!out->values||!out->texts))) { slang_record_mixed_release(out); return 0; }
    for(size_t f=0;f<out->fields;++f) out->types[f]=src->types[f];
    /* Copy selected rows including owned text. */
    if(src->fields) {
        size_t dst=0;
        for(size_t row=0;row<src->rows;++row) {
            if(!slang_record_mixed_eval(src,row,program,instructions,text_pool,text_count,stack,&sp,&res)||res.type!=1||!res.boolean) continue;
            for(size_t f=0;f<src->fields;++f) { size_t si=row*src->fields+f,di=dst*src->fields+f; out->values[di]=src->values[si]; if(src->types[f]==2) { size_t n=strlen(src->texts[si])+1; out->texts[di]=(char*)malloc(n); if(!out->texts[di]) { slang_record_mixed_release(out); return 0; } memcpy(out->texts[di],src->texts[si],n); } }
            ++dst;
        }
    }
    return (int64_t)(uintptr_t)out;
}

SLANG_API int64_t slang_record_mixed_map_fields_expr(int64_t handle,const int64_t *program,long instructions,const char *const *text_pool,long text_count) {
    SlangRecordMixedCollection *src=slang_record_mixed_ptr(handle);
    if(!src||!program||instructions<=0) return 0;
    SlangRecordMixedCollection *out=(SlangRecordMixedCollection*)calloc(1,sizeof(*out));
    if(!out) return 0; out->rows=src->rows; out->fields=src->fields;
    out->types=out->fields?(int*)calloc(out->fields,sizeof(int)):NULL;
    size_t total=out->rows*out->fields;
    out->values=total?(uint64_t*)calloc(total,sizeof(uint64_t)):NULL;
    out->texts=total?(char**)calloc(total,sizeof(char*)):NULL;
    if((out->fields&&!out->types)||(total&&(!out->values||!out->texts))) { slang_record_mixed_release(out); return 0; }
    for(size_t f=0;f<out->fields;++f) out->types[f]=src->types[f];
    for(size_t i=0;i<total;++i) {
        out->values[i]=src->values[i];
        if(src->types[i%src->fields]==2) { size_t n=strlen(src->texts[i])+1; out->texts[i]=(char*)malloc(n); if(!out->texts[i]) { slang_record_mixed_release(out); return 0; } memcpy(out->texts[i],src->texts[i],n); }
    }
    SlangMixedValue stack[256]; int sp;
    for(size_t row=0;row<src->rows;++row) {
        sp=0;
        for(long pc=0;pc<instructions;++pc) {
            const int64_t *ins=program+pc*5; int op=(int)ins[0];
            if(op==26) {
                long target=ins[1], source=ins[2];
                if(target<0||source<0||(size_t)target>=out->fields||(size_t)source>=src->fields||out->types[target]!=src->types[source]) { slang_record_mixed_release(out); return 0; }
                size_t si=row*src->fields+(size_t)source, di=row*out->fields+(size_t)target;
                out->values[di]=src->values[si];
                if(out->types[target]==2) {
                    free(out->texts[di]);
                    const char *text=src->texts[si]?src->texts[si]:"";
                    size_t n=strlen(text)+1; out->texts[di]=(char*)malloc(n);
                    if(!out->texts[di]) { slang_record_mixed_release(out); return 0; }
                    memcpy(out->texts[di],text,n);
                }
            } else if(op==20) {
                if(sp<1||ins[1]<0||(size_t)ins[1]>=out->fields) { slang_record_mixed_release(out); return 0; }
                SlangMixedValue v=stack[--sp]; int tf=out->types[ins[1]]; size_t di=row*out->fields+(size_t)ins[1];
                if(v.type!=tf) { slang_record_mixed_release(out); return 0; }
                if(tf==0) memcpy(&out->values[di],&v.num,sizeof(double));
                else if(tf==1) out->values[di]=(uint64_t)(v.boolean!=0);
                else { free(out->texts[di]); size_t n=strlen(v.text?v.text:"")+1; out->texts[di]=(char*)malloc(n); if(!out->texts[di]) { slang_record_mixed_release(out); return 0; } memcpy(out->texts[di],v.text?v.text:"",n); }
            } else if(op==0) { if(!slang_mixed_push(stack,&sp,1,0,ins[1]!=0,NULL)) { slang_record_mixed_release(out); return 0; } }
            else if(op==1) { if(!slang_mixed_push(stack,&sp,0,slang_bits_f64(ins[4]),0,NULL)) { slang_record_mixed_release(out); return 0; } }
            else if(op==3) {
                long f=ins[1]; int t=(int)ins[2]; if(f<0||(size_t)f>=src->fields||src->types[f]!=t) { slang_record_mixed_release(out); return 0; }
                size_t idx=row*src->fields+(size_t)f;
                if(t==0) { if(!slang_mixed_push(stack,&sp,0,slang_bits_f64((int64_t)src->values[idx]),0,NULL)) { slang_record_mixed_release(out); return 0; } }
                else if(t==1) { if(!slang_mixed_push(stack,&sp,1,0,src->values[idx]!=0,NULL)) { slang_record_mixed_release(out); return 0; } }
                else { if(!slang_mixed_push(stack,&sp,2,0,0,src->texts[idx])) { slang_record_mixed_release(out); return 0; } }
            } else if(op==23) { long ti=ins[1]; if(ti<0||ti>=text_count||!text_pool||!slang_mixed_push(stack,&sp,2,0,0,text_pool[ti])) { slang_record_mixed_release(out); return 0; } }
            else if(op>=4&&op<=8) {
                if(sp<2||stack[sp-1].type!=0||stack[sp-2].type!=0) { slang_record_mixed_release(out); return 0; }
                double b=stack[--sp].num,a=stack[--sp].num,v=(op==4)?a+b:(op==5)?a-b:(op==6)?a*b:(op==7)?a/b:pow(a,b); if(!slang_mixed_push(stack,&sp,0,v,0,NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op>=10&&op<=15) {
                if(sp<2||stack[sp-1].type!=0||stack[sp-2].type!=0) { slang_record_mixed_release(out); return 0; }
                double b=stack[--sp].num,a=stack[--sp].num; if(!slang_mixed_push(stack,&sp,1,0,slang_record_mixed_compare_num(a,b,op-10),NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==21||op==22) {
                if(sp<2||stack[sp-1].type!=2||stack[sp-2].type!=2) { slang_record_mixed_release(out); return 0; }
                const char*b=stack[--sp].text,*a=stack[--sp].text; if(!slang_mixed_push(stack,&sp,1,0,slang_record_mixed_compare_text(a,b,op==21?4:5),NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==24||op==25) {
                if(sp<2||stack[sp-1].type!=1||stack[sp-2].type!=1) { slang_record_mixed_release(out); return 0; }
                int b=stack[--sp].boolean,a=stack[--sp].boolean; if(!slang_mixed_push(stack,&sp,1,0,op==24?(a==b):(a!=b),NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==16||op==17) {
                if(sp<2||stack[sp-1].type!=1||stack[sp-2].type!=1) { slang_record_mixed_release(out); return 0; }
                int b=stack[--sp].boolean,a=stack[--sp].boolean; if(!slang_mixed_push(stack,&sp,1,0,op==16?(a&&b):(a||b),NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==18) { if(sp<1||stack[sp-1].type!=1) { slang_record_mixed_release(out); return 0; } stack[sp-1].boolean=!stack[sp-1].boolean; }
            else if(op==19) { if(sp<3||stack[sp-3].type!=1) { slang_record_mixed_release(out); return 0; } SlangMixedValue e=stack[--sp],t=stack[--sp],c=stack[--sp]; if(t.type!=e.type) { slang_record_mixed_release(out); return 0; } stack[sp++]=c.boolean?t:e; }
            else { slang_record_mixed_release(out); return 0; }
        }
        if(sp!=0) { slang_record_mixed_release(out); return 0; }
    }
    return (int64_t)(uintptr_t)out;
}


/* Schema-changing mixed Record map (1.10.47). The target schema is explicit; every
 * constructor argument is evaluated against the original source row and stored
 * into its corresponding target field. No field-count/name compatibility is
 * assumed, and result types must exactly match target types. */
SLANG_API int64_t slang_record_mixed_map_to_schema_expr(int64_t handle,
                                              const int64_t *types, long fields,
                                              const int64_t *program, long instructions,
                                              const char *const *text_pool, long text_count) {
    SlangRecordMixedCollection *src=slang_record_mixed_ptr(handle);
    if(!src||fields<0||!types||!program||instructions<=0) return 0;
    SlangRecordMixedCollection *out=(SlangRecordMixedCollection*)calloc(1,sizeof(*out));
    if(!out) return 0;
    out->rows=src->rows; out->fields=(size_t)fields;
    out->types=out->fields?(int*)calloc(out->fields,sizeof(int)):NULL;
    size_t total=out->rows*out->fields;
    out->values=total?(uint64_t*)calloc(total,sizeof(uint64_t)):NULL;
    out->texts=total?(char**)calloc(total,sizeof(char*)):NULL;
    if((out->fields&&!out->types)||(total&&(!out->values||!out->texts))) { slang_record_mixed_release(out); return 0; }
    for(size_t f=0;f<out->fields;++f) {
        if(types[f]<0||types[f]>2) { slang_record_mixed_release(out); return 0; }
        out->types[f]=(int)types[f];
    }
    SlangMixedValue stack[256]; int sp;
    for(size_t row=0;row<src->rows;++row) {
        sp=0;
        for(long pc=0;pc<instructions;++pc) {
            const int64_t *ins=program+pc*5; int op=(int)ins[0];
            if(op==26) {
                long target=ins[1], source=ins[2];
                if(target<0||source<0||(size_t)target>=out->fields||(size_t)source>=src->fields||out->types[target]!=src->types[source]) { slang_record_mixed_release(out); return 0; }
                size_t si=row*src->fields+(size_t)source, di=row*out->fields+(size_t)target;
                out->values[di]=src->values[si];
                if(out->types[target]==2) {
                    free(out->texts[di]);
                    const char *text=src->texts[si]?src->texts[si]:"";
                    size_t n=strlen(text)+1; out->texts[di]=(char*)malloc(n);
                    if(!out->texts[di]) { slang_record_mixed_release(out); return 0; }
                    memcpy(out->texts[di],text,n);
                }
            } else if(op==20) {
                if(sp<1||ins[1]<0||(size_t)ins[1]>=out->fields) { slang_record_mixed_release(out); return 0; }
                SlangMixedValue v=stack[--sp]; int tf=out->types[ins[1]]; size_t di=row*out->fields+(size_t)ins[1];
                if(v.type!=tf) { slang_record_mixed_release(out); return 0; }
                if(tf==0) memcpy(&out->values[di],&v.num,sizeof(double));
                else if(tf==1) out->values[di]=(uint64_t)(v.boolean!=0);
                else {
                    size_t n=strlen(v.text?v.text:"")+1; out->texts[di]=(char*)malloc(n);
                    if(!out->texts[di]) { slang_record_mixed_release(out); return 0; }
                    memcpy(out->texts[di],v.text?v.text:"",n);
                }
            } else if(op==0) {
                if(!slang_mixed_push(stack,&sp,1,0,ins[1]!=0,NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==1) {
                if(!slang_mixed_push(stack,&sp,0,slang_bits_f64(ins[4]),0,NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==3) {
                long f=ins[1]; int t=(int)ins[2];
                if(f<0||(size_t)f>=src->fields||src->types[f]!=t) { slang_record_mixed_release(out); return 0; }
                size_t idx=row*src->fields+(size_t)f;
                if(t==0) { if(!slang_mixed_push(stack,&sp,0,slang_bits_f64((int64_t)src->values[idx]),0,NULL)) { slang_record_mixed_release(out); return 0; } }
                else if(t==1) { if(!slang_mixed_push(stack,&sp,1,0,src->values[idx]!=0,NULL)) { slang_record_mixed_release(out); return 0; } }
                else { if(!slang_mixed_push(stack,&sp,2,0,0,src->texts[idx])) { slang_record_mixed_release(out); return 0; } }
            } else if(op==23) {
                long ti=ins[1];
                if(ti<0||ti>=text_count||!text_pool||!slang_mixed_push(stack,&sp,2,0,0,text_pool[ti])) { slang_record_mixed_release(out); return 0; }
            } else if(op>=4&&op<=8) {
                if(sp<2||stack[sp-1].type!=0||stack[sp-2].type!=0) { slang_record_mixed_release(out); return 0; }
                double b=stack[--sp].num,a=stack[--sp].num,v=(op==4)?a+b:(op==5)?a-b:(op==6)?a*b:(op==7)?a/b:pow(a,b);
                if(!slang_mixed_push(stack,&sp,0,v,0,NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op>=10&&op<=15) {
                if(sp<2||stack[sp-1].type!=0||stack[sp-2].type!=0) { slang_record_mixed_release(out); return 0; }
                double b=stack[--sp].num,a=stack[--sp].num;
                if(!slang_mixed_push(stack,&sp,1,0,slang_record_mixed_compare_num(a,b,op-10),NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==21||op==22) {
                if(sp<2||stack[sp-1].type!=2||stack[sp-2].type!=2) { slang_record_mixed_release(out); return 0; }
                const char*b=stack[--sp].text,*a=stack[--sp].text;
                if(!slang_mixed_push(stack,&sp,1,0,slang_record_mixed_compare_text(a,b,op==21?4:5),NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==24||op==25) {
                if(sp<2||stack[sp-1].type!=1||stack[sp-2].type!=1) { slang_record_mixed_release(out); return 0; }
                int b=stack[--sp].boolean,a=stack[--sp].boolean;
                if(!slang_mixed_push(stack,&sp,1,0,op==24?(a==b):(a!=b),NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==16||op==17) {
                if(sp<2||stack[sp-1].type!=1||stack[sp-2].type!=1) { slang_record_mixed_release(out); return 0; }
                int b=stack[--sp].boolean,a=stack[--sp].boolean;
                if(!slang_mixed_push(stack,&sp,1,0,op==16?(a&&b):(a||b),NULL)) { slang_record_mixed_release(out); return 0; }
            } else if(op==18) {
                if(sp<1||stack[sp-1].type!=1) { slang_record_mixed_release(out); return 0; } stack[sp-1].boolean=!stack[sp-1].boolean;
            } else if(op==19) {
                if(sp<3||stack[sp-3].type!=1) { slang_record_mixed_release(out); return 0; }
                SlangMixedValue e=stack[--sp],t=stack[--sp],c=stack[--sp]; if(t.type!=e.type) { slang_record_mixed_release(out); return 0; } stack[sp++]=c.boolean?t:e;
            } else { slang_record_mixed_release(out); return 0; }
        }
        if(sp!=0) { slang_record_mixed_release(out); return 0; }
    }
    return (int64_t)(uintptr_t)out;
}

/* reduce op follows slang_reduce_f64: 0 +, 1 -, 2 *, 3 /. */
SLANG_API double slang_collection_f64_reduce(int64_t handle, double initial, int op) {
    SlangF64Collection *c = slang_f64_collection_ptr(handle);
    if (!c) return initial;
    return slang_reduce_f64(c->values, (long)c->count, initial, op);
}

/* aggregate op: 0 sum, 1 min, 2 max, 3 count */
SLANG_API double slang_collection_f64_aggregate(int64_t handle, int op) {
    SlangF64Collection *c = slang_f64_collection_ptr(handle);
    if (!c) return 0.0;
    if (op == 3) return (double)c->count;
    if (c->count == 0) return 0.0;
    if (op == 0) return slang_reduce_f64(c->values, (long)c->count, 0.0, 0);
    double result = c->values[0];
    for (size_t i = 1; i < c->count; ++i) {
        if (op == 1 && c->values[i] < result) result = c->values[i];
        else if (op == 2 && c->values[i] > result) result = c->values[i];
    }
    return result;
}

/* 1.15.72: runtime CSV source for native data pipelines. */
typedef struct {
    size_t rows;
    size_t cols;
    char **headers;
    char **cells;
} SlangCsvTable;

static void slang_csv_free_table(SlangCsvTable *t) {
    if (!t) return;
    if (t->headers) { for (size_t i=0;i<t->cols;++i) free(t->headers[i]); free(t->headers); }
    if (t->cells) { for (size_t i=0;i<t->rows*t->cols;++i) free(t->cells[i]); free(t->cells); }
    free(t);
}

static char *slang_csv_next_field(const char **cursor, int *done) {
    const char *p = *cursor;
    size_t cap = 64, n = 0;
    char *out = (char *)malloc(cap);
    if (!out) return NULL;
    int quoted = 0;
    if (*p == '"') { quoted = 1; ++p; }
    for (;;) {
        char c = *p;
        if (quoted) {
            if (c == '"') {
                if (p[1] == '"') { c = '"'; ++p; }
                else { quoted = 0; ++p; continue; }
            }
        } else if (c == ',' || c == '\n' || c == '\r' || c == '\0') {
            break;
        }
        if (n + 1 >= cap) {
            cap *= 2;
            char *grown = (char *)realloc(out, cap);
            if (!grown) { free(out); return NULL; }
            out = grown;
        }
        out[n++] = c;
        ++p;
    }
    out[n] = '\0';
    while (!quoted && n > 0 && isspace((unsigned char)out[n-1])) out[--n] = '\0';
    if (*p == ',') { *cursor = p + 1; *done = 0; }
    else {
        int row_end = (*p == '\n' || *p == '\r');
        if (*p == '\r' && p[1] == '\n') ++p;
        if (*p == '\n' || *p == '\r') ++p;
        *cursor = p; *done = row_end || (*p == '\0');
    }
    return out;
}

static int slang_csv_parse_line(const char **cursor, char ***fields_out, size_t *count_out, int *eof_out) {
    size_t cap = 8, count = 0;
    char **fields = (char **)calloc(cap, sizeof(char *));
    if (!fields) return 0;
    int done = 0;
    while (!done) {
        if (count == cap) {
            cap *= 2;
            char **grown = (char **)realloc(fields, cap * sizeof(char *));
            if (!grown) { for (size_t i=0;i<count;++i) free(fields[i]); free(fields); return 0; }
            fields = grown;
        }
        fields[count] = slang_csv_next_field(cursor, &done);
        if (!fields[count]) { for (size_t i=0;i<count;++i) free(fields[i]); free(fields); return 0; }
        ++count;
    }
    *fields_out = fields; *count_out = count; *eof_out = 0;
    return 1;
}

SLANG_API int64_t slang_csv_open(const char *path) {
    char *text = slang_file_read(path);
    if (!text) return 0;
    SlangCsvTable *t = (SlangCsvTable *)calloc(1, sizeof(SlangCsvTable));
    if (!t) { free(text); return 0; }
    const char *cursor = text;
    char **headers = NULL; size_t cols = 0; int eof = 0;
    if (*cursor == '\0' || !slang_csv_parse_line(&cursor, &headers, &cols, &eof) || cols == 0) {
        free(text); slang_csv_free_table(t); return 0;
    }
    t->headers = headers; t->cols = cols;
    size_t row_cap = 64;
    t->cells = (char **)calloc(row_cap * cols, sizeof(char *));
    if (!t->cells) { free(text); slang_csv_free_table(t); return 0; }
    while (*cursor) {
        char **fields = NULL; size_t field_count = 0;
        if (!slang_csv_parse_line(&cursor, &fields, &field_count, &eof)) { free(text); slang_csv_free_table(t); return 0; }
        if (field_count == 1 && fields[0][0] == '\0' && *cursor == '\0') { free(fields[0]); free(fields); break; }
        if (t->rows == row_cap) {
            row_cap *= 2;
            char **grown = (char **)realloc(t->cells, row_cap * cols * sizeof(char *));
            if (!grown) { for (size_t i=0;i<field_count;++i) free(fields[i]); free(fields); free(text); slang_csv_free_table(t); return 0; }
            t->cells = grown;
            memset(t->cells + t->rows * cols, 0, (row_cap - t->rows) * cols * sizeof(char *));
        }
        for (size_t c=0;c<cols;++c) {
            if (c < field_count) t->cells[t->rows * cols + c] = fields[c];
            else t->cells[t->rows * cols + c] = slang_strdup("");
        }
        for (size_t c=cols;c<field_count;++c) free(fields[c]);
        free(fields);
        ++t->rows;
    }
    free(text);
    return (int64_t)(intptr_t)t;
}

SLANG_API long slang_csv_count(int64_t handle) {
    SlangCsvTable *t = (SlangCsvTable *)(intptr_t)handle;
    return t ? (long)t->rows : 0;
}

SLANG_API long slang_csv_field_index(int64_t handle, const char *name) {
    SlangCsvTable *t = (SlangCsvTable *)(intptr_t)handle;
    if (!t || !name) return -1;
    for (size_t i=0;i<t->cols;++i) if (strcmp(t->headers[i], name) == 0) return (long)i;
    return -1;
}

SLANG_API const char *slang_csv_get_text(int64_t handle, long row, long field) {
    SlangCsvTable *t = (SlangCsvTable *)(intptr_t)handle;
    if (!t || row < 0 || field < 0 || (size_t)row >= t->rows || (size_t)field >= t->cols) return "";
    return t->cells[(size_t)row * t->cols + (size_t)field];
}

SLANG_API double slang_to_number(const char *text) {
    if (!text) return 0.0;
    char *end = NULL;
    double value = strtod(text, &end);
    while (end && *end && isspace((unsigned char)*end)) ++end;
    if (end == text || (end && *end != '\0')) {
        fprintf(stderr, "S-Lang: to_number failed for '%s'\n", text);
        exit(1);
    }
    return value;
}

SLANG_API void slang_csv_free(int64_t handle) {
    slang_csv_free_table((SlangCsvTable *)(intptr_t)handle);
}



/* 1.15.81: native grouped min/max + shared multi-aggregate traversal
   1.15.79: native grouped numeric aggregates over explicit record maps.
   The grouped runtime accumulates CSV numeric fields only when the S-Lang
   pipeline explicitly maps them through to_number into a typed record.
   This preserves the Text boundary of read_csv.

   1.15.78: native materialized CSV sort.  Sorting is stable and compares
   the CSV Text field lexicographically, matching read_csv field semantics. */
typedef struct {
    size_t row;
    const char *key;
} SlangCsvSortEntry;

static int slang_csv_sort_entry_cmp(const void *a, const void *b) {
    const SlangCsvSortEntry *x = (const SlangCsvSortEntry *)a;
    const SlangCsvSortEntry *y = (const SlangCsvSortEntry *)b;
    int c = strcmp(x->key ? x->key : "", y->key ? y->key : "");
    if (c != 0) return c;
    if (x->row < y->row) return -1;
    if (x->row > y->row) return 1;
    return 0;
}

static void slang_csv_sort_merge(SlangCsvSortEntry *a, SlangCsvSortEntry *tmp,
                                 size_t lo, size_t mid, size_t hi) {
    size_t i = lo, j = mid, k = lo;
    while (i < mid && j < hi) {
        if (slang_csv_sort_entry_cmp(&a[i], &a[j]) <= 0) tmp[k++] = a[i++];
        else tmp[k++] = a[j++];
    }
    while (i < mid) tmp[k++] = a[i++];
    while (j < hi) tmp[k++] = a[j++];
    for (k = lo; k < hi; ++k) a[k] = tmp[k];
}

static void slang_csv_sort_merge_recursive(SlangCsvSortEntry *a, SlangCsvSortEntry *tmp,
                                           size_t lo, size_t hi) {
    if (hi - lo <= 1) return;
    size_t mid = lo + (hi - lo) / 2;
    slang_csv_sort_merge_recursive(a, tmp, lo, mid);
    slang_csv_sort_merge_recursive(a, tmp, mid, hi);
    slang_csv_sort_merge(a, tmp, lo, mid, hi);
}

SLANG_API int slang_csv_sort_print(int64_t handle, long field, int ascending) {
    SlangCsvTable *t = (SlangCsvTable *)(intptr_t)handle;
    if (!t || field < 0 || (size_t)field >= t->cols) return 1;
    SlangCsvSortEntry *order = NULL, *tmp = NULL;
    if (t->rows) {
        order = (SlangCsvSortEntry *)malloc(t->rows * sizeof(*order));
        tmp = (SlangCsvSortEntry *)malloc(t->rows * sizeof(*tmp));
        if (!order || !tmp) { free(order); free(tmp); return 1; }
        for (size_t i = 0; i < t->rows; ++i) {
            order[i].row = i;
            order[i].key = t->cells[i * t->cols + (size_t)field];
        }
        slang_csv_sort_merge_recursive(order, tmp, 0, t->rows);
        if (!ascending && t->rows > 1) {
            /* Reverse group order but keep equal-key rows stable. */
            size_t out = 0, end = t->rows;
            while (end > 0) {
                size_t start = end - 1;
                while (start > 0 && strcmp(order[start - 1].key ? order[start - 1].key : "", order[end - 1].key ? order[end - 1].key : "") == 0) --start;
                for (size_t k = start; k < end; ++k) tmp[out++] = order[k];
                end = start;
            }
            for (size_t k = 0; k < t->rows; ++k) order[k] = tmp[k];
        }
    }
    printf("[");
    for (size_t i = 0; i < t->rows; ++i) {
        if (i) printf(", ");
        size_t row = order[i].row;
        printf("row(");
        for (size_t col = 0; col < t->cols; ++col) {
            if (col) printf(", ");
            printf("%s=%s", t->headers[col], t->cells[row * t->cols + col] ? t->cells[row * t->cols + col] : "");
        }
        printf(")");
    }
    printf("]\n");
    free(order); free(tmp);
    return 0;
}

/* 1.15.73: native external-CSV grouped aggregates runtime.
   Results are emitted in first-seen group order, matching the reference
   aggregate module's stable grouping contract for scalar keys. */
typedef struct {
    char *key;
    long count;
    double sum;
} SlangCsvGroup;

static int slang_csv_group_find(SlangCsvGroup *groups, size_t count, const char *key) {
    for (size_t i = 0; i < count; ++i) {
        if (strcmp(groups[i].key ? groups[i].key : "", key ? key : "") == 0) return (int)i;
    }
    return -1;
}


SLANG_API int slang_csv_group_count_where_text_print(int64_t handle, long group_field, long filter_field, const char *filter_value) {
    SlangCsvTable *t = (SlangCsvTable *)(intptr_t)handle;
    if (!t || group_field < 0 || filter_field < 0 || (size_t)group_field >= t->cols || (size_t)filter_field >= t->cols || !filter_value) return 1;
    SlangCsvGroup *groups = NULL;
    size_t count = 0, capacity = 0;
    for (size_t row = 0; row < t->rows; ++row) {
        const char *filter = t->cells[row * t->cols + (size_t)filter_field];
        if (strcmp(filter ? filter : "", filter_value) != 0) continue;
        const char *key = t->cells[row * t->cols + (size_t)group_field];
        int idx = slang_csv_group_find(groups, count, key);
        if (idx < 0) {
            if (count == capacity) {
                size_t next = capacity ? capacity * 2 : 8;
                SlangCsvGroup *grown = (SlangCsvGroup *)realloc(groups, next * sizeof(*groups));
                if (!grown) { for (size_t i=0;i<count;++i) free(groups[i].key); free(groups); return 1; }
                groups = grown; capacity = next;
            }
            idx = (int)count++;
            groups[idx].key = slang_strdup(key ? key : "");
            groups[idx].count = 0;
            groups[idx].sum = 0.0;
            if (!groups[idx].key) { for (size_t i=0;i<count-1;++i) free(groups[i].key); free(groups); return 1; }
        }
        groups[idx].count += 1;
    }
    printf("[");
    for (size_t i=0;i<count;++i) {
        if (i) printf(", ");
        printf("row(key=%s, count=%ld)", groups[i].key, groups[i].count);
    }
    printf("]\n");
    for (size_t i=0;i<count;++i) free(groups[i].key);
    free(groups);
    return 0;
}

SLANG_API int slang_csv_group_numeric_map_print(int64_t handle, long group_field, long value_field, int op) {
    SlangCsvTable *t = (SlangCsvTable *)(intptr_t)handle;
    if (!t || group_field < 0 || value_field < 0 || (size_t)group_field >= t->cols || (size_t)value_field >= t->cols) return 1;
    if (op < 1 || op > 4) return 1;
    SlangCsvGroup *groups = NULL;
    size_t count = 0, capacity = 0;
    for (size_t row = 0; row < t->rows; ++row) {
        const char *key = t->cells[row * t->cols + (size_t)group_field];
        double value = slang_to_number(t->cells[row * t->cols + (size_t)value_field]);
        int idx = slang_csv_group_find(groups, count, key);
        if (idx < 0) {
            if (count == capacity) {
                size_t next = capacity ? capacity * 2 : 8;
                SlangCsvGroup *grown = (SlangCsvGroup *)realloc(groups, next * sizeof(*groups));
                if (!grown) { for (size_t i=0;i<count;++i) free(groups[i].key); free(groups); return 1; }
                groups = grown; capacity = next;
            }
            idx = (int)count++;
            groups[idx].key = slang_strdup(key ? key : "");
            groups[idx].count = 0; groups[idx].sum = value;
            if (!groups[idx].key) { for (size_t i=0;i<count-1;++i) free(groups[i].key); free(groups); return 1; }
        } else {
            groups[idx].sum += value;
        }
        groups[idx].count += 1;
        /* sum is also used as the running value for min/max; the first value
           is already installed above, and subsequent updates select the bound. */
        if (op == 3 && groups[idx].count > 1 && value < groups[idx].sum) groups[idx].sum = value;
        if (op == 4 && groups[idx].count > 1 && value > groups[idx].sum) groups[idx].sum = value;
        if (op == 3 && groups[idx].count > 1) {
            /* Recompute the minimum is impossible from a sum accumulator, so
               keep a separate pass-compatible convention below via an auxiliary
               encoding: this branch is replaced by the dedicated arrays in the
               multi path. */
        }
    }
    /* For single min/max, perform a deterministic second scan. This keeps the
       shared group representation compact while preserving exact semantics. */
    if (op == 3 || op == 4) {
        for (size_t i=0;i<count;++i) {
            int initialized = 0; double bound = 0.0;
            for (size_t row=0; row<t->rows; ++row) {
                const char *key=t->cells[row*t->cols+(size_t)group_field];
                if (strcmp(groups[i].key ? groups[i].key : "", key ? key : "") != 0) continue;
                double v=slang_to_number(t->cells[row*t->cols+(size_t)value_field]);
                if (!initialized || (op==3 ? v<bound : v>bound)) { bound=v; initialized=1; }
            }
            groups[i].sum=bound;
        }
    }
    printf("[");
    for (size_t i = 0; i < count; ++i) {
        if (i) printf(", ");
        if (op == 1) printf("row(key=%s, sum=%.15g)", groups[i].key, groups[i].sum);
        else if (op == 2) printf("row(key=%s, average=%.15g)", groups[i].key, groups[i].count ? groups[i].sum / (double)groups[i].count : 0.0);
        else if (op == 3) printf("row(key=%s, min=%.15g)", groups[i].key, groups[i].sum);
        else printf("row(key=%s, max=%.15g)", groups[i].key, groups[i].sum);
    }
    printf("]\n");
    for (size_t i=0;i<count;++i) free(groups[i].key);
    free(groups);
    return 0;
}

SLANG_API int slang_csv_group_multi_numeric_print(int64_t handle, long group_field, const long *value_fields, const int *ops, long n, long filter_field, const char *filter_value) {
    SlangCsvTable *t = (SlangCsvTable *)(intptr_t)handle;
    if (!t || group_field < 0 || (size_t)group_field >= t->cols || !value_fields || !ops || n <= 0 || n > 16) return 1;
    if (filter_field >= 0 && ((size_t)filter_field >= t->cols || !filter_value)) return 1;
    for (long j = 0; j < n; ++j) {
        if (ops[j] == 0) continue; /* count */
        if (ops[j] != 1 && ops[j] != 2 && ops[j] != 3 && ops[j] != 4) return 1;
        if (value_fields[j] < 0 || (size_t)value_fields[j] >= t->cols) return 1;
    }
    SlangCsvGroup *groups = NULL;
    double *sums = NULL;
    double *mins = NULL;
    double *maxs = NULL;
    size_t count = 0, capacity = 0;
    for (size_t row = 0; row < t->rows; ++row) {
        if (filter_field >= 0) {
            const char *fv = t->cells[row * t->cols + (size_t)filter_field];
            if (strcmp(fv ? fv : "", filter_value) != 0) continue;
        }
        const char *key = t->cells[row * t->cols + (size_t)group_field];
        int idx = slang_csv_group_find(groups, count, key);
        if (idx < 0) {
            if (count == capacity) {
                size_t next = capacity ? capacity * 2 : 8;
                SlangCsvGroup *grown = (SlangCsvGroup *)realloc(groups, next * sizeof(*groups));
                double *sgrown = (double *)realloc(sums, next * (size_t)n * sizeof(*sums));
                double *mingrown = (double *)realloc(mins, next * (size_t)n * sizeof(*mins));
                double *maxgrown = (double *)realloc(maxs, next * (size_t)n * sizeof(*maxs));
                if (!grown || !sgrown || !mingrown || !maxgrown) {
                    if (grown) groups = grown; if (sgrown) sums = sgrown; if (mingrown) mins = mingrown; if (maxgrown) maxs = maxgrown;
                    for (size_t i=0;i<count;++i) free(groups[i].key);
                    free(groups); free(sums); free(mins); free(maxs); return 1;
                }
                groups = grown; sums = sgrown; mins = mingrown; maxs = maxgrown; capacity = next;
            }
            idx = (int)count++;
            groups[idx].key = slang_strdup(key ? key : "");
            groups[idx].count = 0;
            groups[idx].sum = 0.0;
            for (long j=0;j<n;++j) {
                sums[(size_t)idx*(size_t)n+(size_t)j]=0.0;
                mins[(size_t)idx*(size_t)n+(size_t)j]=0.0;
                maxs[(size_t)idx*(size_t)n+(size_t)j]=0.0;
            }
            if (!groups[idx].key) { for (size_t i=0;i<count-1;++i) free(groups[i].key); free(groups); free(sums); return 1; }
        }
        groups[idx].count += 1;
        for (long j = 0; j < n; ++j) {
            if (ops[j] == 0) continue;
            double value = slang_to_number(t->cells[row * t->cols + (size_t)value_fields[j]]);
            size_t off=(size_t)idx*(size_t)n+(size_t)j;
            sums[off] += value;
            if (groups[idx].count == 1 || value < mins[off]) mins[off]=value;
            if (groups[idx].count == 1 || value > maxs[off]) maxs[off]=value;
        }
    }
    for (long j = 0; j < n; ++j) {
        printf("[");
        for (size_t i = 0; i < count; ++i) {
            if (i) printf(", ");
            if (ops[j] == 0) printf("row(key=%s, count=%ld)", groups[i].key, groups[i].count);
            else if (ops[j] == 1) printf("row(key=%s, sum=%.15g)", groups[i].key, sums[i*(size_t)n+(size_t)j]);
            else if (ops[j] == 2) printf("row(key=%s, average=%.15g)", groups[i].key, groups[i].count ? sums[i*(size_t)n+(size_t)j] / (double)groups[i].count : 0.0);
            else if (ops[j] == 3) printf("row(key=%s, min=%.15g)", groups[i].key, mins[i*(size_t)n+(size_t)j]);
            else printf("row(key=%s, max=%.15g)", groups[i].key, maxs[i*(size_t)n+(size_t)j]);
        }
        printf("]\n");
    }
    for (size_t i=0;i<count;++i) free(groups[i].key);
    free(groups); free(sums); free(mins); free(maxs);
    return 0;
}

SLANG_API int slang_csv_group_aggregate_print(int64_t handle, long group_field, long value_field, int op) {
    SlangCsvTable *t = (SlangCsvTable *)(intptr_t)handle;
    if (!t || group_field < 0 || (size_t)group_field >= t->cols) return 1;
    if (op != 0 && (value_field < 0 || (size_t)value_field >= t->cols)) return 1;
    SlangCsvGroup *groups = NULL;
    size_t count = 0, capacity = 0;
    for (size_t row = 0; row < t->rows; ++row) {
        const char *key = t->cells[row * t->cols + (size_t)group_field];
        int idx = slang_csv_group_find(groups, count, key);
        if (idx < 0) {
            if (count == capacity) {
                size_t next = capacity ? capacity * 2 : 8;
                SlangCsvGroup *grown = (SlangCsvGroup *)realloc(groups, next * sizeof(*groups));
                if (!grown) { for (size_t i=0;i<count;++i) free(groups[i].key); free(groups); return 1; }
                groups = grown; capacity = next;
            }
            idx = (int)count++;
            groups[idx].key = slang_strdup(key ? key : "");
            groups[idx].count = 0;
            groups[idx].sum = 0.0;
            if (!groups[idx].key) { for (size_t i=0;i<count-1;++i) free(groups[i].key); free(groups); return 1; }
        }
        groups[idx].count += 1;
        if (op != 0) groups[idx].sum += slang_to_number(t->cells[row * t->cols + (size_t)value_field]);
    }
    printf("[");
    for (size_t i = 0; i < count; ++i) {
        if (i) printf(", ");
        if (op == 0) printf("row(key=%s, count=%ld)", groups[i].key, groups[i].count);
        else if (op == 1) printf("row(key=%s, sum=%.15g)", groups[i].key, groups[i].sum);
        else printf("row(key=%s, average=%.15g)", groups[i].key, groups[i].count ? groups[i].sum / (double)groups[i].count : 0.0);
    }
    printf("]\n");
    for (size_t i=0;i<count;++i) free(groups[i].key);
    free(groups);
    return 0;
}


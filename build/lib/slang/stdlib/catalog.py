"""Human- and machine-readable catalog of the S-Lang standard library."""
from __future__ import annotations

from dataclasses import asdict
from .registry import REGISTRY

# Explicit IO/data helpers are kept separate from the pure registry because
# their behavior depends on external files or process state.
IO_LIBRARY = {
    "read": ("slang.stdlib.files", "IO", "read UTF-8 text from a file", "filesystem"),
    "write": ("slang.stdlib.files", "IO", "write UTF-8 text to a file", "filesystem"),
    "exists": ("slang.stdlib.files", "IO", "test whether a path exists", "filesystem"),
    "now_utc": ("slang.stdlib.datetime", "IO", "read the current UTC instant as ISO-8601 text", "runtime"),
    "today_utc": ("slang.stdlib.datetime", "IO", "read the current UTC date as YYYY-MM-DD", "runtime"),
    "read_csv": ("slang.stdlib.csv", "IO", "read UTF-8 CSV into records", "filesystem"),
    "write_csv": ("slang.stdlib.csv", "IO", "write records as UTF-8 CSV", "filesystem"),
    "read_json": ("slang.stdlib.json", "IO", "read JSON from a UTF-8 file", "filesystem"),
    "write_json": ("slang.stdlib.json", "IO", "write JSON to a UTF-8 file", "filesystem"),
    "file_size": ("slang.stdlib.files", "IO", "read file size", "filesystem"),
    "is_file": ("slang.stdlib.files", "IO", "test whether a path is a file", "filesystem"),
    "is_directory": ("slang.stdlib.files", "IO", "test whether a path is a directory", "filesystem"),
    "list_directory": ("slang.stdlib.files", "IO", "list directory entries", "filesystem"),
    "list_files": ("slang.stdlib.files", "IO", "list files directly contained in a directory", "filesystem"),
    "list_directories": ("slang.stdlib.files", "IO", "list directories directly contained in a directory", "filesystem"),
    "make_directory": ("slang.stdlib.files", "IO", "create a directory", "filesystem"),
    "remove_directory": ("slang.stdlib.files", "IO", "remove an empty directory", "filesystem"),
    "remove_directory_tree": ("slang.stdlib.files", "IO", "remove a directory tree", "filesystem"),
    "read_text": ("slang.stdlib.files", "IO", "read UTF-8 text from a file", "filesystem"),
    "write_text": ("slang.stdlib.files", "IO", "write UTF-8 text to a file", "filesystem"),
    "append_text": ("slang.stdlib.files", "IO", "append UTF-8 text to a file", "filesystem"),
    "read_lines": ("slang.stdlib.files", "IO", "read a UTF-8 text file as lines", "filesystem"),
    "write_lines": ("slang.stdlib.files", "IO", "write text lines to a file", "filesystem"),
    "remove_file": ("slang.stdlib.files", "IO", "remove a file", "filesystem"),
    "copy_file": ("slang.stdlib.files", "IO", "copy a file", "filesystem"),
    "move_file": ("slang.stdlib.files", "IO", "move a file", "filesystem"),
    "make_directories": ("slang.stdlib.files", "IO", "create a directory tree", "filesystem"),
}


def entries() -> list[dict]:
    result = []
    for name in sorted(REGISTRY):
        fn = REGISTRY[name]
        result.append({
            "name": name,
            "kind": "function",
            "effect": fn.effect,
            "capability": fn.capability,
            "module": f"slang.stdlib.{_module_for(name)}",
            "description": _description_for(name, _module_for(name)),
        })
    for name in sorted(IO_LIBRARY):
        module, effect, description, capability = IO_LIBRARY[name]
        result.append({
            "name": name,
            "kind": "function",
            "effect": effect,
            "module": module,
            "description": description,
            "capability": capability,
        })
    return sorted(result, key=lambda row: row["name"])



_MODULE_LABELS = {
    "math": "mathematics", "text": "text processing", "json": "JSON data",
    "datetime": "date and time", "data": "record and field access",
    "aggregate": "grouping and aggregation", "relational": "relational data operations",
    "analytics": "data analytics", "collections": "collection processing",
    "path": "file path handling", "process": "process and environment management",
}

_DESCRIPTION_OVERRIDES = {
    "sqrt": "Return the square root of a number.",
    "trim": "Remove whitespace from the beginning and end of text.",
    "lower": "Convert text to lowercase.", "upper": "Convert text to uppercase.",
    "split": "Split text into a list using a separator.",
    "join_texts": "Join a list of text values with a separator.",
    "json_parse": "Parse JSON text into an S-Lang value.",
    "json_stringify": "Convert a value to compact JSON text.",
    "json_pretty": "Convert a value to indented, readable JSON text.",
    "keys": "Return the field names in a record.",
    "get": "Return the value associated with a record field.",
    "has": "Check whether a record contains a field.",
    "pluck": "Extract one field from each record in a list.",
    "merge_records": "Combine the fields of two records.",
    "group_by": "Group records by the selected field.",
    "group_count": "Count records in each field-value group.",
    "group_sum": "Sum a numeric field within each group.",
    "distinct_by": "Keep one record for each distinct field value.",
    "join_records": "Join two record lists using matching key fields.",
    "order_by": "Sort records by a selected field.",
    "window": "Split records into sliding windows.",
    "take": "Return the first requested number of list items.",
    "skip": "Return the list after skipping the requested number of items.",
    "reverse": "Return the items of a list in reverse order.",
    "sort_numbers": "Return numbers in ascending order.",
    "sum_numbers": "Return the sum of a list of numbers.",
    "average_number": "Return the arithmetic mean of a list of numbers.",
    "median_number": "Return the median of a list of numbers.",
    "find_first": "Return the first item matching a condition.",
    "find_last": "Return the last item matching a condition.",
    "find_all": "Return all items matching a condition.",
    "now_utc": "Return the current UTC instant as ISO-8601 text.",
    "today_utc": "Return the current UTC date as YYYY-MM-DD text.",
    "read_text": "Read a UTF-8 text file.",
    "write_text": "Write text to a UTF-8 file, replacing its contents.",
    "append_text": "Append text to a UTF-8 file.",
    "read_csv": "Read a UTF-8 CSV file as records.",
    "write_csv": "Write records to a UTF-8 CSV file.",
    "read_json": "Read and parse JSON from a UTF-8 file.",
    "write_json": "Write a value as JSON to a UTF-8 file.",
    "run_program": "Run a program with an argument list.",
    "run_program_timeout": "Run a program with a time limit.",
}


def _description_for(name: str, module: str) -> str:
    """Return a concise catalog description for every public entry."""
    if name in _DESCRIPTION_OVERRIDES:
        return _DESCRIPTION_OVERRIDES[name]
    module_name = module.rsplit(".", 1)[-1]
    label = _MODULE_LABELS.get(module_name, module_name.replace("_", " "))
    return f"Standard-library {label} operation: {name.replace('_', ' ')}."

def _module_for(name: str) -> str:
    # Keep this mapping explicit at the public catalog boundary. The registry
    # intentionally stores callable contracts rather than presentation data.
    groups = {
        "abs_number": "math", "sqrt": "math", "exp2_number": "math", "cbrt_number": "math", "log10_number": "math", "log2_number": "math", "floor": "math", "ceil": "math", "round_number": "math", "truncate_number": "math", "fraction_number": "math", "is_even_number": "math", "is_odd_number": "math", "clamp_number": "math", "sign_number": "math", "pow_number": "math", "min_of_numbers": "math", "max_of_numbers": "math", "lerp_number": "math", "log_number": "math", "exp_number": "math", "mod_number": "math", "hypot_number": "math", "degrees_number": "math", "radians_number": "math", "sin_number": "math", "cos_number": "math", "tan_number": "math", "asin_number": "math", "acos_number": "math", "atan_number": "math", "atan2_number": "math", "sinh_number": "math", "cosh_number": "math", "tanh_number": "math", "asinh_number": "math", "acosh_number": "math", "atanh_number": "math", "gcd_number": "math", "lcm_number": "math", "factorial_number": "math", "normalize_number": "math", "remap_number": "math", "is_finite_number": "math", "is_nan_number": "math", "is_integer_number": "math", "reciprocal_number": "math",
        "trim": "text", "lower": "text", "upper": "text", "starts_with": "text", "ends_with": "text", "replace": "text", "split": "text", "contains_text": "text", "index_of": "text", "join_texts": "text", "repeat_text": "text", "length_text": "text", "substring_text": "text", "char_at_text": "text", "pad_left_text": "text", "pad_right_text": "text", "count_text": "text", "remove_prefix_text": "text", "remove_suffix_text": "text", "reverse_text": "text", "normalize_whitespace": "text", "split_lines": "text", "join_lines": "text",
        "json_parse": "json", "json_stringify": "json", "json_pretty": "json", "json_get": "json", "json_has": "json", "json_set": "json", "parse_datetime": "datetime", "format_datetime": "datetime", "add_seconds_datetime": "datetime", "diff_seconds_datetime": "datetime", "add_days_datetime": "datetime", "add_months_datetime": "datetime", "start_of_day_datetime": "datetime", "end_of_day_datetime": "datetime", "date_components_datetime": "datetime", "is_leap_year": "datetime", "days_in_month": "datetime", "weekday_datetime": "datetime", "week_number_datetime": "datetime",
        "keys": "data", "get": "data", "has": "data", "pluck": "data", "select_fields": "data", "merge_records": "data", "remove_field": "data",
        "group_by": "aggregate", "group_count": "aggregate", "group_sum": "aggregate", "group_average": "aggregate", "group_min": "aggregate", "group_max": "aggregate", "frequency": "aggregate", "mode": "aggregate",
        "distinct_by": "relational", "join_records": "relational", "partition": "relational", "order_by": "relational", "find_by": "relational", "count_by": "relational",
        "window": "analytics", "rank_by": "analytics", "top_by": "analytics", "bottom_by": "analytics", "window_sum": "analytics", "window_average": "analytics", "group_top_by": "analytics",
        "reverse": "collections", "sort_numbers": "collections", "take": "collections", "skip": "collections", "chunk": "collections", "flatten_one": "collections", "chunk_exact": "collections", "unique_values": "collections", "concat_values": "collections", "intersect_values": "collections", "difference_values": "collections", "union_values": "collections", "symmetric_difference_values": "collections", "filter_values": "collections", "reject_values": "collections", "map_values": "collections", "map_with_index": "collections", "enumerate_values": "collections", "zip_values": "collections", "unzip_values": "collections", "sliding_windows": "collections", "pairwise": "collections", "sum_numbers": "collections", "cumulative_sum_numbers": "collections", "cumulative_product_numbers": "collections", "cumulative_min_numbers": "collections", "cumulative_max_numbers": "collections", "differences_numbers": "collections", "cumulative_average_numbers": "collections", "percent_change_numbers": "collections", "moving_average_numbers": "collections", "normalize_numbers": "collections", "quantile_number": "collections", "sum_squares_numbers": "collections", "dot_product_numbers": "collections", "l2_norm_numbers": "collections", "euclidean_distance_numbers": "collections", "manhattan_distance_numbers": "collections", "cosine_similarity_numbers": "collections", "z_scores_numbers": "collections", "covariance_numbers": "collections", "correlation_numbers": "collections", "weighted_average_numbers": "collections", "clip_numbers": "collections", "argmin_number": "collections", "argmax_number": "collections", "index_of_number": "collections", "last_index_of_number": "collections", "find_first": "collections", "find_last": "collections", "find_all": "collections", "find_all_indices": "collections", "partition_values": "collections", "partition_indices": "collections", "take_while": "collections", "drop_while": "collections", "take_until": "collections", "drop_until": "collections", "span_while": "collections", "count_if": "collections", "product_numbers": "collections", "average_number": "collections", "median_number": "collections", "variance_number": "collections", "stddev_number": "collections", "min_number": "collections", "max_number": "collections", "count_value": "collections", "contains_value": "collections", "contains_all_values": "collections", "contains_any_value": "collections", "any_true": "collections", "all_true": "collections", "none_true": "collections", "is_empty_values": "collections", "is_not_empty_values": "collections", "is_single_value": "collections", "is_multiple_values": "collections", "is_unique_values": "collections", "has_at_least_values": "collections", "has_at_most_values": "collections", "has_exactly_values": "collections", "take_every_values": "collections", "take_every_from_values": "collections", "split_at_values": "collections", "rotate_values": "collections", "reverse_values": "collections", "reverse_range_values": "collections", "sort_values": "collections", "sort_descending_values": "collections", "sort_by_values": "collections", "group_by_values": "collections", "group_values_by": "collections", "aggregate_values_by": "collections", "aggregate_values_by_with_key": "collections", "aggregate_groups": "collections", "partition_by_values": "collections", "count_by_values": "collections", "index_by_values": "collections", "distinct_by_values": "collections", "min_by_values": "collections", "max_by_values": "collections", "fold_values": "collections", "scan_values": "collections", "scan_values_right": "collections", "running_values": "collections", "running_values_right": "collections",
        "basename": "path", "dirname": "path", "extension": "path", "join_path": "path", "normalize_path": "path",
        "arguments": "process", "argument_count": "process", "argument_at": "process", "environment": "process", "environment_or": "process", "has_environment": "process", "set_environment": "process", "remove_environment": "process", "run_process": "process", "run_program": "process", "run_program_with_environment": "process", "run_process_timeout": "process", "run_program_timeout": "process", "current_directory": "process", "platform_name": "process", "process_id": "process", "sleep_seconds": "process", "home_directory": "process", "temp_directory": "process", "executable_path": "process", "command_exists": "process",
    }
    return groups[name]


def capability_for(name: str) -> str | None:
    """Return declared capability for a registry or catalog stdlib function."""
    fn = REGISTRY.get(name)
    if fn is not None:
        return fn.capability
    entry = IO_LIBRARY.get(name)
    return None if entry is None else entry[3]

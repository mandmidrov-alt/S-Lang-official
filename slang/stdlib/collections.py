from __future__ import annotations

import math


def range_numbers(start: float, stop: float, step: float) -> list[float]:
    """Create a finite, half-open numeric range [start, stop).

    Reject non-numeric/non-finite inputs and steps too small to advance the
    current floating-point value, rather than silently returning a partial
    range or looping forever.
    """
    arguments = (start, stop, step)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in arguments):
        raise TypeError("range_numbers expects numeric start, stop, and step")
    if not all(math.isfinite(value) for value in arguments):
        raise ValueError("range_numbers expects finite start, stop, and step")
    if step == 0:
        raise ValueError("range_numbers step cannot be zero")

    values = []
    current = start
    if step > 0:
        while current < stop:
            values.append(int(current) if isinstance(current, float) and current.is_integer() else current)
            next_value = current + step
            if next_value == current:
                raise ValueError("range_numbers step is too small to advance the current value")
            current = next_value
    else:
        while current > stop:
            values.append(int(current) if isinstance(current, float) and current.is_integer() else current)
            next_value = current + step
            if next_value == current:
                raise ValueError("range_numbers step is too small to advance the current value")
            current = next_value
    return values


def reverse(values: list) -> list:
    return list(reversed(values))


def sort_numbers(values: list[float]) -> list[float]:
    return sorted(values)


def sum_numbers(values: list[float]) -> float:
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("sum_numbers expects List<Number>")
    return sum(values)


def min_number(values: list[float]) -> float:
    if not values:
        raise RuntimeError("min_number cannot operate on an empty List")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("min_number expects List<Number>")
    return min(values)


def max_number(values: list[float]) -> float:
    if not values:
        raise RuntimeError("max_number cannot operate on an empty List")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("max_number expects List<Number>")
    return max(values)


def count_value(values: list, value) -> int:
    return sum(1 for item in values if item == value)


def contains_value(values: list, value) -> bool:
    """Return whether a collection contains the requested value."""
    return any(item == value for item in values)


def contains_all_values(values: list, required: list) -> bool:
    """Return whether every required value occurs in a collection."""
    return all(contains_value(values, value) for value in required)


def contains_any_value(values: list, candidates: list) -> bool:
    """Return whether at least one candidate value occurs in a collection."""
    return any(contains_value(values, value) for value in candidates)


def any_true(values: list[bool]) -> bool:
    if not all(isinstance(value, bool) for value in values):
        raise TypeError("any_true expects List<Boolean>")
    return any(values)


def all_true(values: list[bool]) -> bool:
    if not all(isinstance(value, bool) for value in values):
        raise TypeError("all_true expects List<Boolean>")
    return all(values)


def none_true(values: list[bool]) -> bool:
    """Return whether no value in the collection is true."""
    if not all(isinstance(value, bool) for value in values):
        raise TypeError("none_true expects List<Boolean>")
    return not any(values)


def is_empty_values(values: list) -> bool:
    """Return whether a collection contains no values."""
    return len(values) == 0


def is_not_empty_values(values: list) -> bool:
    """Return whether a collection contains at least one value."""
    return len(values) != 0


def is_single_value(values: list) -> bool:
    """Return whether a collection contains exactly one value."""
    return len(values) == 1

def is_multiple_values(values: list) -> bool:
    """Return whether a collection contains at least two values."""
    return len(values) >= 2


def is_unique_values(values: list) -> bool:
    """Return whether every value in a collection occurs at most once."""
    return all(values[i] != values[j] for i in range(len(values)) for j in range(i + 1, len(values)))


def has_at_least_values(values: list, count: float) -> bool:
    """Return whether a collection contains at least ``count`` values.

    Counts must be finite whole numbers. Integer-valued floats are accepted;
    fractional, boolean, and non-finite counts are rejected consistently with
    ``has_at_most_values`` and ``has_exactly_values``.
    """
    count = _require_integral_index(count, "has_at_least_values", "count")
    if count < 0:
        raise ValueError("has_at_least_values count cannot be negative")
    return len(values) >= count


def has_at_most_values(values: list, count: float) -> bool:
    """Return whether a collection contains at most ``count`` values."""
    count = _require_integral_index(count, "has_at_most_values", "count")
    if count < 0:
        raise ValueError("has_at_most_values count cannot be negative")
    return len(values) <= count


def has_exactly_values(values: list, count: float) -> bool:
    """Return whether a collection contains exactly ``count`` values."""
    count = _require_integral_index(count, "has_exactly_values", "count")
    if count < 0:
        raise ValueError("has_exactly_values count cannot be negative")
    return len(values) == count


def take_every_values(values: list, step: float) -> list:
    """Return every ``step``-th value, starting with the first value."""
    step = _require_integral_index(step, "take_every_values", "step")
    if step <= 0:
        raise ValueError("take_every_values step must be positive")
    return list(values[::step])


def take_every_from_values(values: list, step: float, start: float) -> list:
    """Return every ``step``-th value starting at zero-based ``start``."""
    step = _require_integral_index(step, "take_every_from_values", "step")
    start = _require_integral_index(start, "take_every_from_values", "start")
    if step <= 0:
        raise ValueError("take_every_from_values step must be positive")
    if start < 0:
        raise ValueError("take_every_from_values start cannot be negative")
    return list(values[start::step])


def split_at_values(values: list, index: float) -> list:
    """Split a collection at a zero-based whole-number index, preserving order."""
    index = _require_integral_index(index, "split_at_values", "index")
    if index < 0:
        index = 0
    if index > len(values):
        index = len(values)
    return [list(values[:index]), list(values[index:])]


def rotate_values(values: list, shift: float) -> list:
    """Rotate a collection left by a whole-number ``shift``; negative shifts rotate right."""
    shift = _require_integral_index(shift, "rotate_values", "shift")
    if not values:
        return []
    shift = shift % len(values)
    return list(values[shift:]) + list(values[:shift])


def reverse_values(values: list) -> list:
    """Return a collection in reverse order without mutating the input."""
    return list(reversed(values))


def sort_values(values: list) -> list:
    """Return a stable sorted copy; values must be mutually comparable."""
    try:
        return sorted(values)
    except TypeError as exc:
        raise TypeError(
            "sort_values cannot compare every item; use values of a compatible type "
            "or provide an explicit sort key with sort_by_values"
        ) from exc

def sort_descending_values(values: list) -> list:
    """Return a stable descending sorted copy; values must be mutually comparable."""
    try:
        return sorted(values, reverse=True)
    except TypeError as exc:
        raise TypeError(
            "sort_descending_values cannot compare every item; use values of a compatible type "
            "or provide an explicit sort key with sort_by_values"
        ) from exc

def sort_by_values(values: list, key) -> list:
    """Return a stable sorted copy using a key function without mutating the input."""
    if not callable(key):
        raise TypeError("sort_by_values expects a callable key")
    try:
        return sorted(values, key=key)
    except TypeError as exc:
        raise TypeError(
            "sort_by_values could not compare the computed sort keys; make the key function "
            "return mutually comparable values of a consistent type"
        ) from exc



def _require_hashable_key(value, function_name: str):
    """Raise a domain-specific error when a computed collection key cannot index a map/set."""
    try:
        hash(value)
    except TypeError as exc:
        raise TypeError(
            f"{function_name} computed an unhashable key; return a simple value such as Text, Number, or Boolean"
        ) from exc
    return value


def group_by_values(values: list, key) -> dict:
    """Group collection values by a computed key, preserving encounter order."""
    if not callable(key):
        raise TypeError("group_by_values expects a callable key")
    groups = {}
    for value in values:
        group_key = _require_hashable_key(key(value), "group_by_values")
        groups.setdefault(group_key, []).append(value)
    return groups

def group_values_by(values: list, key, value) -> dict:
    """Group projected values by a computed key, preserving encounter order."""
    if not callable(key):
        raise TypeError("group_values_by expects a callable key")
    if not callable(value):
        raise TypeError("group_values_by expects a callable value")
    groups = {}
    for item in values:
        group_key = _require_hashable_key(key(item), "group_values_by")
        groups.setdefault(group_key, []).append(value(item))
    return groups


def aggregate_values_by(values: list, key, aggregate) -> dict:
    """Group values by a computed key and aggregate each group directly."""
    if not callable(key):
        raise TypeError("aggregate_values_by expects a callable key")
    if not callable(aggregate):
        raise TypeError("aggregate_values_by expects a callable aggregate")
    groups = {}
    for value in values:
        group_key = _require_hashable_key(key(value), "aggregate_values_by")
        groups.setdefault(group_key, []).append(value)
    return {group_key: aggregate(group) for group_key, group in groups.items()}


def aggregate_values_by_with_key(values: list, key, aggregate) -> dict:
    """Group values by a computed key and aggregate each group with its key."""
    if not callable(key):
        raise TypeError("aggregate_values_by_with_key expects a callable key")
    if not callable(aggregate):
        raise TypeError("aggregate_values_by_with_key expects a callable aggregate")
    groups = {}
    for value in values:
        group_key = _require_hashable_key(key(value), "aggregate_values_by_with_key")
        groups.setdefault(group_key, []).append(value)
    return {group_key: aggregate(group_key, group) for group_key, group in groups.items()}


def aggregate_groups(values: list, key, aggregate) -> dict:
    """Group values by a computed key and aggregate each group."""
    if not callable(key):
        raise TypeError("aggregate_groups expects a callable key")
    if not callable(aggregate):
        raise TypeError("aggregate_groups expects a callable aggregate")
    groups = {}
    for value in values:
        group_key = _require_hashable_key(key(value), "aggregate_groups")
        groups.setdefault(group_key, []).append(value)
    return {group_key: aggregate(group) for group_key, group in groups.items()}


def partition_by_values(values: list, key) -> dict:
    """Partition collection values into groups by a computed key, preserving encounter order."""
    if not callable(key):
        raise TypeError("partition_by_values expects a callable key")
    partitions = {}
    for value in values:
        partition_key = _require_hashable_key(key(value), "partition_by_values")
        partitions.setdefault(partition_key, []).append(value)
    return partitions

def count_by_values(values: list, key) -> dict:
    """Count collection values by a computed key, preserving key encounter order."""
    if not callable(key):
        raise TypeError("count_by_values expects a callable key")
    counts = {}
    for value in values:
        group_key = _require_hashable_key(key(value), "count_by_values")
        counts[group_key] = counts.get(group_key, 0) + 1
    return counts


def index_by_values(values: list, key) -> dict:
    """Index collection values by a computed key; duplicate keys are rejected."""
    if not callable(key):
        raise TypeError("index_by_values expects a callable key")
    index = {}
    for value in values:
        index_key = _require_hashable_key(key(value), "index_by_values")
        if index_key in index:
            raise ValueError(
                "index_by_values requires unique computed keys; a duplicate was found, so choose a key that uniquely identifies each item"
            )
        index[index_key] = value
    return index


def distinct_by_values(values: list, key) -> list:
    """Return first-seen values with duplicate computed keys removed."""
    if not callable(key):
        raise TypeError("distinct_by_values expects a callable key")
    seen = set()
    result = []
    for value in values:
        distinct_key = _require_hashable_key(key(value), "distinct_by_values")
        if distinct_key in seen:
            continue
        seen.add(distinct_key)
        result.append(value)
    return result


def fold_values(values: list, initial, combine):
    """Fold collection values from left to right into one accumulated result."""
    if not callable(combine):
        raise TypeError("fold_values expects a callable combine")
    accumulator = initial
    for value in values:
        accumulator = combine(accumulator, value)
    return accumulator


def scan_values(values: list, initial, combine) -> list:
    """Return all intermediate left-to-right fold results."""
    if not callable(combine):
        raise TypeError("scan_values expects a callable combine")
    accumulator = initial
    result = []
    for value in values:
        accumulator = combine(accumulator, value)
        result.append(accumulator)
    return result


def running_values(values: list, combine) -> list:
    """Return cumulative results using the first value as the initial accumulator."""
    if not callable(combine):
        raise TypeError("running_values expects a callable combine")
    if not values:
        return []
    accumulator = values[0]
    result = [accumulator]
    for value in values[1:]:
        accumulator = combine(accumulator, value)
        result.append(accumulator)
    return result


def running_values_right(values: list, combine) -> list:
    """Return cumulative results using the last value as the initial accumulator, scanning right-to-left."""
    if not callable(combine):
        raise TypeError("running_values_right expects a callable combine")
    if not values:
        return []
    accumulator = values[-1]
    result = [accumulator]
    for value in reversed(values[:-1]):
        accumulator = combine(accumulator, value)
        result.append(accumulator)
    result.reverse()
    return result


def scan_values_right(values: list, initial, combine) -> list:
    """Return all intermediate right-to-left fold results in left-to-right order."""
    if not callable(combine):
        raise TypeError("scan_values_right expects a callable combine")
    accumulator = initial
    result = []
    for value in reversed(values):
        accumulator = combine(accumulator, value)
        result.append(accumulator)
    result.reverse()
    return result


def max_by_values(values: list, key):
    """Return the first value with the largest computed key."""
    if not callable(key):
        raise TypeError("max_by_values expects a callable key")
    if not values:
        raise ValueError("max_by_values cannot operate on an empty collection")
    iterator = iter(values)
    best = next(iterator)
    best_key = key(best)
    for value in iterator:
        value_key = key(value)
        if value_key > best_key:
            best = value
            best_key = value_key
    return best


def min_by_values(values: list, key):
    """Return the first value with the smallest computed key."""
    if not callable(key):
        raise TypeError("min_by_values expects a callable key")
    if not values:
        raise ValueError("min_by_values cannot operate on an empty collection")
    iterator = iter(values)
    best = next(iterator)
    best_key = key(best)
    for value in iterator:
        value_key = key(value)
        if value_key < best_key:
            best = value
            best_key = value_key
    return best



def _require_integral_index(value, function_name: str, argument_name: str) -> int:
    """Validate a finite, integer-valued numeric count or index."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{function_name} expects a numeric {argument_name}")
    # Python integers are finite by definition, and converting an enormous
    # integer through math.isfinite can raise OverflowError. Only floats need
    # an explicit finiteness check.
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{function_name} expects a finite {argument_name}")
    if int(value) != value:
        raise ValueError(f"{function_name} expects a whole-number {argument_name}")
    return int(value)


def reverse_range_values(values: list, start: float, end: float) -> list:
    """Return a copy with the half-open range [start, end) reversed.

    Bounds must be finite whole numbers; values outside the collection are
    clamped to its edges, and an empty/reversed interval leaves it unchanged.
    """
    start = _require_integral_index(start, "reverse_range_values", "start")
    end = _require_integral_index(end, "reverse_range_values", "end")
    result = list(values)
    n = len(result)
    start = max(0, min(n, start))
    end = max(0, min(n, end))
    if start < end:
        result[start:end] = reversed(result[start:end])
    return result


def take(values: list, count: float) -> list:
    """Return the first ``count`` items from a collection."""
    count = _require_integral_index(count, "take", "count")
    if count < 0:
        raise ValueError("take count cannot be negative")
    return list(values[:count])


def skip(values: list, count: float) -> list:
    """Return a collection after skipping the first ``count`` items."""
    count = _require_integral_index(count, "skip", "count")
    if count < 0:
        raise ValueError("skip count cannot be negative")
    return list(values[count:])


def chunk(values: list, size: float) -> list[list]:
    """Split a collection into consecutive chunks of at most ``size`` items."""
    size = _require_integral_index(size, "chunk", "size")
    if size <= 0:
        raise ValueError("chunk size must be positive")
    return [list(values[i:i + size]) for i in range(0, len(values), size)]


def pairwise(values: list) -> list[list]:
    """Return consecutive overlapping pairs; fewer than two items yields []."""
    return [[values[i], values[i + 1]] for i in range(max(0, len(values) - 1))]


def product_numbers(values: list[float]) -> float:
    """Multiply all numeric values; the empty product is 1."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("product_numbers expects List<Number>")
    result = 1
    for value in values:
        result *= value
    return result


def average_number(values: list[float]) -> float:
    """Return the arithmetic mean of a non-empty numeric collection."""
    if not values:
        raise RuntimeError("average_number cannot operate on an empty List")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("average_number expects List<Number>")
    return sum(values) / len(values)


def median_number(values: list[float]) -> float:
    """Return the median of a non-empty numeric collection."""
    if not values:
        raise RuntimeError("median_number cannot operate on an empty List")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("median_number expects List<Number>")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def variance_number(values: list[float]) -> float:
    """Return the population variance of a non-empty numeric collection."""
    if not values:
        raise RuntimeError("variance_number cannot operate on an empty List")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("variance_number expects List<Number>")
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def stddev_number(values: list[float]) -> float:
    """Return the population standard deviation of a non-empty numeric collection."""
    import math
    return math.sqrt(variance_number(values))

def cumulative_sum_numbers(values: list[float]) -> list[float]:
    """Return running sums for a numeric collection."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("cumulative_sum_numbers expects List<Number>")
    result = []
    total = 0
    for value in values:
        total += value
        result.append(total)
    return result


def cumulative_product_numbers(values: list[float]) -> list[float]:
    """Return running products for a numeric collection."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("cumulative_product_numbers expects List<Number>")
    result = []
    total = 1
    for value in values:
        total *= value
        result.append(total)
    return result



def cumulative_min_numbers(values: list[float]) -> list[float]:
    """Return running minimum values for a numeric collection."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("cumulative_min_numbers expects List<Number>")
    if not values:
        return []
    result = []
    current = values[0]
    for value in values:
        if value < current:
            current = value
        result.append(current)
    return result


def cumulative_max_numbers(values: list[float]) -> list[float]:
    """Return running maximum values for a numeric collection."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("cumulative_max_numbers expects List<Number>")
    if not values:
        return []
    result = []
    current = values[0]
    for value in values:
        if value > current:
            current = value
        result.append(current)
    return result



def cumulative_average_numbers(values: list[float]) -> list[float]:
    """Return the running arithmetic mean for a numeric collection."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("cumulative_average_numbers expects List<Number>")
    result = []
    total = 0
    for index, value in enumerate(values, start=1):
        total += value
        result.append(total / index)
    return result


def percent_change_numbers(values: list[float]) -> list[float]:
    """Return adjacent percentage changes: ((current - previous) / previous) * 100."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("percent_change_numbers expects List<Number>")
    if len(values) < 2:
        return []
    result = []
    for previous, current in zip(values, values[1:]):
        if previous == 0:
            raise RuntimeError("percent_change_numbers cannot divide by zero")
        result.append(((current - previous) / previous) * 100)
    return result

def differences_numbers(values: list[float]) -> list[float]:
    """Return adjacent differences: value[i] - value[i-1]."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("differences_numbers expects List<Number>")
    if len(values) < 2:
        return []
    return [values[i] - values[i - 1] for i in range(1, len(values))]

def moving_average_numbers(values: list[float], window: float) -> list[float]:
    """Return simple moving averages over consecutive numeric windows."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("moving_average_numbers expects List<Number>")
    if isinstance(window, bool) or not isinstance(window, (int, float)):
        raise TypeError("moving_average_numbers expects a numeric window")
    window = int(window)
    if window <= 0:
        raise ValueError("moving_average_numbers window must be positive")
    if window > len(values):
        return []
    return [sum(values[i:i + window]) / window for i in range(len(values) - window + 1)]


def quantile_number(values: list[float], q: float) -> float:
    """Return the linearly interpolated quantile for q in [0, 1]."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("quantile_number expects List<Number>")
    if isinstance(q, bool) or not isinstance(q, (int, float)):
        raise TypeError("quantile_number expects a numeric quantile")
    if not values:
        raise RuntimeError("quantile_number cannot operate on an empty List")
    if q < 0 or q > 1:
        raise ValueError("quantile_number q must be between 0 and 1")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def sum_squares_numbers(values: list[float]) -> float:
    """Return the sum of squared numeric values."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("sum_squares_numbers expects List<Number>")
    return sum(value * value for value in values)


def dot_product_numbers(left: list[float], right: list[float]) -> float:
    """Return the numeric dot product of two equally sized lists."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in left):
        raise TypeError("dot_product_numbers expects List<Number> for left")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in right):
        raise TypeError("dot_product_numbers expects List<Number> for right")
    if len(left) != len(right):
        raise ValueError("dot_product_numbers expects lists of equal length")
    return sum(a * b for a, b in zip(left, right))


def l2_norm_numbers(values: list[float]) -> float:
    """Return the Euclidean (L2) norm of numeric values."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("l2_norm_numbers expects List<Number>")
    return sum(value * value for value in values) ** 0.5


def euclidean_distance_numbers(left: list[float], right: list[float]) -> float:
    """Return Euclidean distance between two equally sized numeric lists."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in left):
        raise TypeError("euclidean_distance_numbers expects List<Number> for left")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in right):
        raise TypeError("euclidean_distance_numbers expects List<Number> for right")
    if len(left) != len(right):
        raise ValueError("euclidean_distance_numbers expects lists of equal length")
    return sum((a - b) * (a - b) for a, b in zip(left, right)) ** 0.5


def manhattan_distance_numbers(left: list[float], right: list[float]) -> float:
    """Return Manhattan (L1) distance between two equally sized numeric lists."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in left):
        raise TypeError("manhattan_distance_numbers expects List<Number> for left")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in right):
        raise TypeError("manhattan_distance_numbers expects List<Number> for right")
    if len(left) != len(right):
        raise ValueError("manhattan_distance_numbers expects lists of equal length")
    return sum(abs(a - b) for a, b in zip(left, right))


def cosine_similarity_numbers(left: list[float], right: list[float]) -> float:
    """Return cosine similarity between two equally sized numeric lists."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in left):
        raise TypeError("cosine_similarity_numbers expects List<Number> for left")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in right):
        raise TypeError("cosine_similarity_numbers expects List<Number> for right")
    if len(left) != len(right):
        raise ValueError("cosine_similarity_numbers expects lists of equal length")
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        raise ValueError("cosine_similarity_numbers is undefined for a zero vector")
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def z_scores_numbers(values: list[float]) -> list[float]:
    """Return population-standard-deviation z-scores for numeric values."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("z_scores_numbers expects List<Number>")
    if not values:
        return []
    mean = sum(values) / len(values)
    variance = sum((value - mean) * (value - mean) for value in values) / len(values)
    if variance == 0:
        return [0.0 for _ in values]
    deviation = variance ** 0.5
    return [(value - mean) / deviation for value in values]


def covariance_numbers(left: list[float], right: list[float]) -> float:
    """Return population covariance between two equally sized numeric lists."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in left):
        raise TypeError("covariance_numbers expects List<Number> for left")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in right):
        raise TypeError("covariance_numbers expects List<Number> for right")
    if len(left) != len(right):
        raise ValueError("covariance_numbers expects lists of equal length")
    if not left:
        raise ValueError("covariance_numbers is undefined for empty lists")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    return sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right)) / len(left)


def correlation_numbers(left: list[float], right: list[float]) -> float:
    """Return Pearson correlation between two equally sized numeric lists."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in left):
        raise TypeError("correlation_numbers expects List<Number> for left")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in right):
        raise TypeError("correlation_numbers expects List<Number> for right")
    if len(left) != len(right):
        raise ValueError("correlation_numbers expects lists of equal length")
    if not left:
        raise ValueError("correlation_numbers is undefined for empty lists")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_ss = sum((value - left_mean) * (value - left_mean) for value in left)
    right_ss = sum((value - right_mean) * (value - right_mean) for value in right)
    if left_ss == 0 or right_ss == 0:
        raise ValueError("correlation_numbers is undefined for a constant list")
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    return covariance / (left_ss * right_ss) ** 0.5


def normalize_numbers(values: list[float]) -> list[float]:
    """Normalize numeric values to the [0, 1] interval using min-max scaling."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("normalize_numbers expects List<Number>")
    if not values:
        return []
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return [0.0 for _ in values]
    span = maximum - minimum
    return [(value - minimum) / span for value in values]



def clip_numbers(values: list[float], minimum: float, maximum: float) -> list[float]:
    """Clamp every numeric value to the inclusive [minimum, maximum] interval."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("clip_numbers expects List<Number>")
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)):
        raise TypeError("clip_numbers expects Number for minimum")
    if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
        raise TypeError("clip_numbers expects Number for maximum")
    if minimum > maximum:
        raise ValueError("clip_numbers requires minimum <= maximum")
    return [min(max(value, minimum), maximum) for value in values]


def argmin_number(values: list[float]) -> int:
    """Return the index of the first minimum numeric value."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("argmin_number expects List<Number>")
    if not values:
        raise RuntimeError("argmin_number cannot operate on an empty List")
    return min(range(len(values)), key=lambda index: values[index])


def argmax_number(values: list[float]) -> int:
    """Return the index of the first maximum numeric value."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("argmax_number expects List<Number>")
    if not values:
        raise RuntimeError("argmax_number cannot operate on an empty List")
    return max(range(len(values)), key=lambda index: values[index])


def weighted_average_numbers(values: list[float], weights: list[float]) -> float:
    """Return the weighted arithmetic mean of two equal-length numeric lists."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("weighted_average_numbers expects List<Number> for values")
    if not all(isinstance(weight, (int, float)) and not isinstance(weight, bool) for weight in weights):
        raise TypeError("weighted_average_numbers expects List<Number> for weights")
    if len(values) != len(weights):
        raise ValueError("weighted_average_numbers expects equal-length lists")
    if not values:
        raise RuntimeError("weighted_average_numbers cannot operate on an empty List")
    total_weight = sum(weights)
    if total_weight == 0:
        raise RuntimeError("weighted_average_numbers requires a non-zero total weight")
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def index_of_number(values: list[float], target: float) -> int:
    """Return the first index of target in a numeric collection, or -1."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("index_of_number expects List<Number>")
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        raise TypeError("index_of_number expects Number for target")
    for index, value in enumerate(values):
        if value == target:
            return index
    return -1


def last_index_of_number(values: list[float], target: float) -> int:
    """Return the last index of target in a numeric collection, or -1."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError("last_index_of_number expects List<Number>")
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        raise TypeError("last_index_of_number expects Number for target")
    for index in range(len(values) - 1, -1, -1):
        if values[index] == target:
            return index
    return -1

def find_first(values, predicate):
    """Return the first index whose value satisfies predicate, or -1."""
    if not callable(predicate):
        raise TypeError("find_first expects a callable predicate")
    for index, value in enumerate(values):
        if predicate(value):
            return index
    return -1


def find_last(values, predicate):
    """Return the last index whose value satisfies predicate, or -1."""
    if not callable(predicate):
        raise TypeError("find_last expects a callable predicate")
    for index in range(len(values) - 1, -1, -1):
        if predicate(values[index]):
            return index
    return -1


def find_all(values, predicate):
    """Return all values that satisfy predicate, preserving input order."""
    if not callable(predicate):
        raise TypeError("find_all expects a callable predicate")
    return [value for value in values if predicate(value)]


def count_if(values, predicate):
    """Return the number of values that satisfy predicate."""
    if not callable(predicate):
        raise TypeError("count_if expects a callable predicate")
    return sum(1 for value in values if predicate(value))


def find_all_indices(values, predicate):
    """Return all indices whose values satisfy predicate, preserving order."""
    if not callable(predicate):
        raise TypeError("find_all_indices expects a callable predicate")
    return [index for index, value in enumerate(values) if predicate(value)]


def partition_values(values, predicate):
    """Split values into matching and non-matching lists, preserving order."""
    if not callable(predicate):
        raise TypeError("partition expects a callable predicate")
    matching = []
    non_matching = []
    for value in values:
        (matching if predicate(value) else non_matching).append(value)
    return [matching, non_matching]


def partition_indices(values, predicate):
    """Split indices into matching and non-matching lists, preserving order."""
    if not callable(predicate):
        raise TypeError("partition_indices expects a callable predicate")
    matching = []
    non_matching = []
    for index, value in enumerate(values):
        (matching if predicate(value) else non_matching).append(index)
    return [matching, non_matching]


def take_while(values, predicate):
    """Return the longest prefix whose values satisfy predicate."""
    if not callable(predicate):
        raise TypeError("take_while expects a callable predicate")
    result = []
    for value in values:
        if not predicate(value):
            break
        result.append(value)
    return result


def drop_while(values, predicate):
    """Return the suffix after the longest prefix whose values satisfy predicate."""
    if not callable(predicate):
        raise TypeError("drop_while expects a callable predicate")
    index = 0
    while index < len(values) and predicate(values[index]):
        index += 1
    return list(values[index:])


def span_while(values, predicate):
    """Split values into the longest matching prefix and the remaining suffix."""
    if not callable(predicate):
        raise TypeError("span_while expects a callable predicate")
    index = 0
    while index < len(values) and predicate(values[index]):
        index += 1
    return [list(values[:index]), list(values[index:])]


def drop_until(values, predicate):
    """Return the suffix starting at the first element that satisfies predicate."""
    if not callable(predicate):
        raise TypeError("drop_until expects a callable predicate")
    for index, value in enumerate(values):
        if predicate(value):
            return list(values[index:])
    return []


def take_until(values, predicate):
    """Return values before the first element that satisfies predicate."""
    if not callable(predicate):
        raise TypeError("take_until expects a callable predicate")
    result = []
    for value in values:
        if predicate(value):
            break
        result.append(value)
    return result



def flatten_one(values):
    """Flatten one list nesting level while preserving element order."""
    result = []
    for group in values:
        if not isinstance(group, (list, tuple)):
            raise TypeError("flatten_one expects a list of lists")
        result.extend(group)
    return result


def unique_values(values):
    """Return unique values in first-seen order."""
    result = []
    seen = set()
    for value in values:
        try:
            marker = (type(value), value)
            if marker in seen:
                continue
            seen.add(marker)
        except TypeError:
            if any(existing == value for existing in result):
                continue
        result.append(value)
    return result


def concat_values(left, right):
    """Concatenate two collections into a new collection, preserving order."""
    return list(left) + list(right)


def intersect_values(left, right):
    """Return unique values present in both collections, preserving left order."""
    result = []
    for value in left:
        if any(existing == value for existing in result):
            continue
        if any(value == candidate for candidate in right):
            result.append(value)
    return result


def difference_values(left, right):
    """Return unique values present in left but not right, preserving left order."""
    result = []
    for value in left:
        if any(existing == value for existing in result):
            continue
        if not any(value == candidate for candidate in right):
            result.append(value)
    return result


def union_values(left, right):
    """Return unique values from both collections, preserving first-seen order."""
    result = []
    for value in list(left) + list(right):
        if any(existing == value for existing in result):
            continue
        result.append(value)
    return result


def symmetric_difference_values(left, right):
    """Return unique values present in exactly one collection, preserving order."""
    result = []
    for value in list(left) + list(right):
        if any(existing == value for existing in result):
            continue
        in_left = any(value == candidate for candidate in left)
        in_right = any(value == candidate for candidate in right)
        if in_left != in_right:
            result.append(value)
    return result


def filter_values(values, predicate):
    """Keep values for which predicate returns true, preserving input order."""
    if not callable(predicate):
        raise TypeError("filter_values expects a callable predicate")
    return [value for value in values if predicate(value)]


def reject_values(values, predicate):
    """Keep values for which predicate returns false, preserving input order."""
    if not callable(predicate):
        raise TypeError("reject_values expects a callable predicate")
    return [value for value in values if not predicate(value)]


def map_values(values, mapper):
    """Apply mapper to each value and return transformed values in input order."""
    if not callable(mapper):
        raise TypeError("map_values expects a callable mapper")
    return [mapper(value) for value in values]


def map_with_index(values, mapper):
    """Apply a mapper to each value together with its zero-based index."""
    if not callable(mapper):
        raise TypeError("map_with_index expects a callable mapper")
    return [mapper(value, index) for index, value in enumerate(values)]


def zip_values(left, right):
    """Pair values from two collections up to the length of the shorter collection."""
    return [[left[index], right[index]] for index in range(min(len(left), len(right)))]


def enumerate_values(values):
    """Return [index, value] pairs using zero-based indices."""
    return [[index, value] for index, value in enumerate(values)]


def unzip_values(pairs):
    """Split a collection of two-value pairs into two collections."""
    left = []
    right = []
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("unzip_values expects pairs with exactly two values")
        left.append(pair[0])
        right.append(pair[1])
    return [left, right]


def chunk_exact(values, size):
    """Split into full-size chunks; size must be a finite whole number."""
    size = _require_integral_index(size, "chunk_exact", "size")
    if size <= 0:
        raise ValueError("chunk_exact size must be positive")
    return [list(values[index:index + size]) for index in range(0, len(values) - size + 1, size)]


def sliding_windows(values, size, step=1):
    """Return overlapping fixed-size windows; size and step must be whole numbers."""
    size = _require_integral_index(size, "sliding_windows", "size")
    step = _require_integral_index(step, "sliding_windows", "step")
    if size <= 0:
        raise ValueError("sliding_windows size must be positive")
    if step <= 0:
        raise ValueError("sliding_windows step must be positive")
    return [list(values[index:index + size]) for index in range(0, max(0, len(values) - size + 1), step)]

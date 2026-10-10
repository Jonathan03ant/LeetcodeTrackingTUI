"""Trace functions for array-based algorithms."""

from collections.abc import Iterator

from ..state import ArrayRange, ArrayState


def _sort_colors_state(
    nums: list[int], low: int, mid: int, high: int, message: str
) -> ArrayState:
    ranges = (
        ArrayRange(0, low - 1, "0s", "bold white on dark_green"),
        ArrayRange(low, mid - 1, "1s", "bold black on bright_yellow"),
        ArrayRange(mid, high, "unprocessed", "bold white on dark_red"),
        ArrayRange(high + 1, len(nums) - 1, "2s", "bold white on dark_blue"),
    )
    return ArrayState(
        values=tuple(nums),
        pointers=(("low", low), ("mid", mid), ("high", high)),
        ranges=ranges,
        highlights=frozenset({mid}) if 0 <= mid < len(nums) else frozenset(),
        message=message,
    )


def trace_sort_colors(values: list[int]) -> Iterator[ArrayState]:
    """Yield Dutch National Flag states without mutating the caller's list."""
    if any(value not in (0, 1, 2) for value in values):
        raise ValueError("Sort Colors accepts only 0, 1, and 2")

    nums = values.copy()
    low = 0
    mid = 0
    high = len(nums) - 1

    yield _sort_colors_state(
        nums,
        low,
        mid,
        high,
        "Start: everything from mid through high is unprocessed.",
    )

    while mid <= high:
        current = nums[mid]

        if current == 0:
            old_low = low
            old_mid = mid
            nums[low], nums[mid] = nums[mid], nums[low]
            low += 1
            mid += 1
            message = (
                f"nums[{old_mid}] is 0: swap indices {old_mid} and {old_low}; "
                "advance low and mid."
            )
        elif current == 1:
            old_mid = mid
            mid += 1
            message = f"nums[{old_mid}] is 1: it is already in place; advance mid."
        else:
            old_mid = mid
            old_high = high
            nums[mid], nums[high] = nums[high], nums[mid]
            high -= 1
            message = (
                f"nums[{old_mid}] is 2: swap indices {old_mid} and {old_high}; "
                "decrease high but keep mid because the incoming value is unprocessed."
            )

        yield _sort_colors_state(nums, low, mid, high, message)

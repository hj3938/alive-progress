import math
import operator

from .utils import overlay_sliding_window_factory, repeating, spinner_player, \
    static_sliding_window_factory


def frame_spinner_factory(*frames):
    """Create a factory of a spinner that delivers frames in sequence.

    Args:
        frames (str): the frames to be displayed
            if sent only one, it is interpreted as frames of one char each.

    Returns:
        a styled spinner factory

    """

    def inner_factory(length_actual=None):
        @repeating(length_actual)
        def inner_spinner():
            yield from frames

        inner_spinner.cycles = len(frames)
        return inner_spinner

    if len(frames) == 1:
        frames = frames[0]

    inner_factory.natural = len(frames[0])
    return inner_factory


def scrolling_spinner_factory(chars, length=None, block=None, background=None,
                              right=True, hiding=True, overlay=False):
    """Create a factory of a spinner that scrolls characters from one side to
    the other, configurable with various constraints.

    Args:
        chars (str): the characters to be scrolled, either together or split in blocks
        length (Optional[int]): the natural length that should be used in the style
        block (Optional[int]): if defined, split chars in blocks with this size
        background (Optional[str]): the pattern to be used besides or underneath the animations
        right (bool): the scroll direction to animate
        hiding (bool): controls whether the animation goes outside the borders or stays inside
        overlay (bool): fixes the background in place if overlay, scrolls it otherwise

    Returns:
        a styled spinner factory

    """

    def inner_factory(length_actual=None):
        if block and not (length_actual or length):  # pragma: no cover
            raise ValueError('length must be set with block')

        ratio = float(length_actual) / length if length and length_actual else 1
        length_actual = length_actual or inner_factory.natural

        def inner_spinner():
            for _ in range(inner_spinner.cycles):
                yield next(infinite_ribbon)

        initial, block_size = 0, int((block or 0) * ratio) or len(chars)
        if hiding:
            gap = length_actual
        else:
            gap = max(0, length_actual - block_size)
            if right:
                initial = -block_size if block else abs(length_actual - block_size)

        if block:
            contents = map(lambda c: c * block_size, reversed(chars) if right else chars)
        else:
            contents = (chars,)

        window_impl = overlay_sliding_window_factory if overlay else static_sliding_window_factory
        infinite_ribbon = window_impl(background, gap, contents, length_actual, step, initial)

        inner_spinner.cycles = gap + block_size
        return inner_spinner

    step = -1 if right else 1
    background = background or ' '

    inner_factory.natural = length or len(chars)
    return inner_factory


def bouncing_spinner_factory(right_chars, length, block=None, left_chars=None,
                             blank=' ', hiding=True):
    """Create a factory of a spinner that bounces characters inside a line."""

    def inner_factory(length_actual=None):
        right_scroll = scrolling_spinner_factory(right_chars, length, block=block, blank=blank,
                                                 right=True, hiding=hiding)(length_actual)
        left_scroll = scrolling_spinner_factory(left_chars, length, block=block, blank=blank,
                                                right=False, hiding=hiding)(length_actual)

        ratio = float(length_actual) / length if length and length_actual else 1
        length_actual = length_actual or inner_factory.natural

        @repeating(length_actual)
        def inner_spinner():
            for i, fill in enumerate(right_scroll()):
                if i < right_direction_size:
                    yield fill
            for i, fill in enumerate(left_scroll()):
                if i < left_direction_size:
                    yield fill

        right_block_size = int((block or 0) * ratio) or len(right_chars)
        left_block_size = int((block or 0) * ratio) or len(left_chars)
        right_direction_size = length_actual + right_block_size \
            if hiding else abs(length_actual - right_block_size) or 1
        left_direction_size = length_actual + left_block_size \
            if hiding else abs(length_actual - left_block_size) or 1

        inner_spinner.cycles = right_direction_size + left_direction_size
        return inner_spinner

    left_chars = left_chars or right_chars

    inner_factory.natural = length
    return inner_factory


def compound_spinner_factory(*spinner_factories):
    """Create a factory of a spinner that combines any other spinners together."""

    def inner_factory(length_actual=None):
        @repeating(length_actual)
        def inner_spinner():
            for fills in zip(range(inner_spinner.cycles), *players):
                yield ''.join(fills[1:])

        # this could be weighted on the natural length of the factories,
        # but they will usually be the same types of factories.
        each_length = length_actual and int(math.ceil(length_actual / len(spinner_factories)))
        spinners = [factory(each_length) for factory in spinner_factories]
        op_cycles = operator.attrgetter('cycles')
        longest = max(spinners, key=op_cycles)
        players = [spinner_player(x) for x in spinners]

        inner_spinner.cycles = longest.cycles
        inner_spinner.players = players
        return inner_spinner

    op_natural = operator.attrgetter('natural')
    inner_factory.natural = sum(map(op_natural, spinner_factories))
    return inner_factory


def delayed_spinner_factory(spinner_factory, copies, offset):
    """Create a factory of a spinner that copies itself several times,
    with an increasing iteration offset between them.
    """

    # this spinner is not actually a spinner, it is more a helper factory method.
    # it does not define an inner_spinner, only creates a compound spinner internally.
    def inner_factory(length_actual=None):
        # it needed to have two levels to wait for the length_actual, since this
        # argument can change the number of copies.
        copies_actual = math.ceil(length_actual / spinner_factory.natural) \
            if length_actual else copies
        result = compound_spinner_factory(*((spinner_factory,) * copies_actual))(length_actual)
        for i, s in enumerate(result.players):
            for _ in range(i * offset):
                next(s)
        return result

    inner_factory.natural = spinner_factory.natural * copies
    return inner_factory

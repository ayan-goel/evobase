"""Patch template library.

Each template handles one specific optimization type.
All templates implement the PatchTemplate protocol.
"""

from runner.patchgen.templates.base import PatchTemplate
from runner.patchgen.templates.set_membership import SetMembershipTemplate
from runner.patchgen.templates.json_parse_cache import JsonParseCacheTemplate
from runner.patchgen.templates.string_concat_loop import StringConcatLoopTemplate
from runner.patchgen.templates.sync_fs import SyncFsTemplate
from runner.patchgen.templates.regex_in_loop import RegexInLoopTemplate
from runner.patchgen.templates.array_find_map import ArrayFindMapTemplate
from runner.patchgen.templates.redundant_spread import RedundantSpreadTemplate
from runner.patchgen.templates.memoize_pure import MemoizePureTemplate
from runner.patchgen.templates.loop_intermediate import LoopIntermediateTemplate
from runner.patchgen.templates.dead_code import DeadCodeTemplate

# Registry: maps opportunity type -> template class
TEMPLATE_REGISTRY: dict[str, type[PatchTemplate]] = {
    "set_membership": SetMembershipTemplate,
    "json_parse_cache": JsonParseCacheTemplate,
    "string_concat_loop": StringConcatLoopTemplate,
    "sync_fs_in_handler": SyncFsTemplate,
    "regex_in_loop": RegexInLoopTemplate,
    "unindexed_find": ArrayFindMapTemplate,
    "redundant_spread": RedundantSpreadTemplate,
    "memoize_pure": MemoizePureTemplate,
    "loop_intermediate": LoopIntermediateTemplate,
    "dead_code": DeadCodeTemplate,
}

__all__ = [
    "PatchTemplate",
    "TEMPLATE_REGISTRY",
    "SetMembershipTemplate",
    "JsonParseCacheTemplate",
    "StringConcatLoopTemplate",
    "SyncFsTemplate",
    "RegexInLoopTemplate",
    "ArrayFindMapTemplate",
    "RedundantSpreadTemplate",
    "MemoizePureTemplate",
    "LoopIntermediateTemplate",
    "DeadCodeTemplate",
]

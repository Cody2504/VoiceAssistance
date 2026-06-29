"""Cross-view consistency: map mixed-video positions to original-video clips.

A MomentMix row's `org_clip_ids_order` ([[vid, [s, e]], ...]) places slice
[s, e) of `vid`'s feature file at consecutive positions of the mixed video.
Entries whose vid equals the row's own vid exist in BOTH views (mixed and
original) -> they are the consistency pairs; donor entries are skipped.

Returns [(mixed_start, mixed_end, src_start, src_end), ...], end-exclusive,
in clip units. Pure python, torch-free (shared by the dataset patch and tests).
"""


def build_consistency_map(org_clip_ids_order, own_vid):
    if not org_clip_ids_order:
        return []
    out, pos = [], 0
    for vid, (s, e) in org_clip_ids_order:
        n = e - s
        if vid == own_vid:
            out.append((pos, pos + n, s, e))
        pos += n
    return out

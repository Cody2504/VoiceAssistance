# Agent Tool-Trajectory Eval — 107 cases

- Routing F1 (macro): **0.806**
- Argument correctness: **0.796**
- Mean TaskCompletion: **0.787**
- Mean AnswerRelevancy: **0.938**

## Per-tool routing

| tool | precision | recall |
|---|---|---|
| ask_video_local | 1.00 | 1.00 |
| combine_clips | 0.00 | 0.00 |
| find_concept_mentions | 0.64 | 1.00 |
| find_concept_relations | 1.00 | 0.86 |
| find_index_concepts | 0.86 | 1.00 |
| find_scene_by_image | 1.00 | 1.00 |
| find_sequence | 1.00 | 1.00 |
| find_similar | 1.00 | 1.00 |
| find_sounds | 1.00 | 1.00 |
| get_highlights | 1.00 | 1.00 |
| ground_video | 0.90 | 0.90 |
| moderate_video | 1.00 | 1.00 |
| search_corpus | 0.60 | 1.00 |
| search_index | 1.00 | 0.43 |
| search_motion | 0.00 | 0.00 |
| search_scene_by_image | 1.00 | 1.00 |
| search_video_local | 0.70 | 1.00 |

## Confusion (expected -> predicted)

| expected | predicted | n |
|---|---|---|
| ask_video_local | ask_video_local | 7 |
| combine_clips | ground_video | 1 |
| combine_clips | search_video_local | 2 |
| find_concept_mentions | find_concept_mentions | 7 |
| find_concept_relations | find_concept_relations | 6 |
| find_concept_relations | find_index_concepts | 1 |
| find_index_concepts | find_index_concepts | 6 |
| find_scene_by_image | find_scene_by_image | 6 |
| find_sequence | find_sequence | 4 |
| find_similar | find_similar | 6 |
| find_sounds | find_sounds | 6 |
| get_highlights | get_highlights | 6 |
| ground_video | ground_video | 9 |
| ground_video | search_video_local | 1 |
| moderate_video | moderate_video | 3 |
| search_corpus | search_corpus | 9 |
| search_index | find_concept_mentions | 4 |
| search_index | search_index | 3 |
| search_motion | search_corpus | 6 |
| search_scene_by_image | search_scene_by_image | 7 |
| search_video_local | search_video_local | 7 |

## Failures

| id | expected | predicted | tool_ok | arg_ok |
|---|---|---|---|---|
| edit-1 | combine_clips | search_video_local | False | None |
| edit-2 | combine_clips | search_video_local | False | None |
| disambig-relations-not-mentions | find_concept_relations | find_concept_relations | True | False |
| disambig-mentions-not-relations | find_concept_mentions | find_concept_mentions | True | False |
| kgm-0 | find_concept_mentions | find_concept_mentions | True | False |
| kgm-1 | find_concept_mentions | find_concept_mentions | True | False |
| kgm-2 | find_concept_mentions | find_concept_mentions | True | False |
| kgm-3 | find_concept_mentions | find_concept_mentions | True | False |
| kgm-4 | find_concept_mentions | find_concept_mentions | True | False |
| kgm-5 | find_concept_mentions | find_concept_mentions | True | False |
| kgr-0 | find_concept_relations | find_concept_relations | True | False |
| kgr-1 | find_concept_relations | find_concept_relations | True | False |
| kgr-2 | find_concept_relations | find_concept_relations | True | False |
| kgr-3 | find_concept_relations | find_concept_relations | True | False |
| kgr-4 | find_concept_relations | find_concept_relations | True | False |
| kgr-5 | find_concept_relations | find_index_concepts | True | False |
| kgc-0 | find_index_concepts | find_index_concepts | True | False |
| kgc-1 | find_index_concepts | find_index_concepts | True | False |
| kgc-2 | find_index_concepts | find_index_concepts | True | False |
| kgc-3 | find_index_concepts | find_index_concepts | True | False |
| kgc-4 | find_index_concepts | find_index_concepts | True | False |
| kgc-5 | find_index_concepts | find_index_concepts | True | False |
| ground-4 | ground_video | search_video_local | False | None |
| motion-0 | search_motion | search_corpus | False | None |
| motion-1 | search_motion | search_corpus | False | None |
| motion-2 | search_motion | search_corpus | False | None |
| motion-3 | search_motion | search_corpus | False | None |
| motion-4 | search_motion | search_corpus | False | None |
| motion-5 | search_motion | search_corpus | False | None |

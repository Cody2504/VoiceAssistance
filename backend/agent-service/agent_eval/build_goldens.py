"""Generate the agent_eval golden dataset (~100 cases across all routable tools).

Run:  python -m agent_eval.build_goldens
Emits one YAML file per tool-family into agent_eval/goldens/ (clears existing *.yaml).
Edit the per-tool lists below to extend coverage; queries are deliberately diverse
in phrasing so the routing benchmark exercises real disambiguation.
"""
from pathlib import Path

import yaml

OUT = Path(__file__).parent / "goldens"

# Stable, fake-but-UUID-ish ids. For --live runs, swap these for real corpus ids.
V = {
    "bball": "vid-bball-1", "soccer": "vid-soccer-1", "cook": "vid-cook-1",
    "cook2": "vid-cook-2", "ml": "vid-ml-3", "news": "vid-news-1",
    "concert": "vid-concert-1", "tennis": "vid-tennis-1", "nature": "vid-nature-1",
    "tut": "vid-tutorial-1", "newattach": "vid-NEW-attached",
}
IDX = {"ml": "idx-ml-101", "cook": "idx-cook-201", "hist": "idx-hist-301"}


def case(cid, query, tool, args, fake, context=None, reference=None):
    c = {
        "id": cid,
        "query": query,
        "context": context or {},
        "expected_tools": [{"name": tool, "args": args}],
        "fake_outputs": {tool: fake},
    }
    if reference:
        c["reference_answer"] = reference
    return c


# ---- fake-output builders (enough signal for reflect to answer relevantly) ----
def fo_shots(topic, vid="vid-corpus-1", group="video"):
    return {"query": topic, "group_by": group, "shots": [
        {"video_id": vid, "original_filename": f"{vid}.mp4", "t_start": 0.0, "t_end": 6.0,
         "caption": f"{topic}", "asr_text": f"talking about {topic}", "score": 0.74, "idx": 0},
        {"video_id": vid, "original_filename": f"{vid}.mp4", "t_start": 6.0, "t_end": 12.0,
         "caption": f"more {topic}", "score": 0.58, "idx": 1},
    ]}


def fo_local(topic, vid):
    return {"video_id": vid, "shots": [
        {"idx": 3, "t_start": 30.0, "t_end": 36.0, "asr_text": f"{topic}", "score": 0.66}]}


def fo_moments(topic, vid):
    return {"video_id": vid, "moments": [
        {"t_start": 41.0, "t_end": 47.0, "label": topic, "score": 0.9, "source": "grounding"}]}


def fo_highlights(vid):
    return {"video_id": vid, "duration_s": 120.0, "moments": [
        {"t_start": 12.0, "t_end": 18.0, "score": 0.95},
        {"t_start": 61.0, "t_end": 66.0, "score": 0.88}], "modality_used": "video"}


def fo_scene_local(vid):
    return {"video_id": vid, "matched_scene": {"idx": 2, "t_start": 12.0, "t_end": 15.0, "score": 0.88},
            "ranked_scenes": [{"idx": 2, "t_start": 12.0, "t_end": 15.0, "score": 0.88}]}


def fo_scene_corpus(vid):
    return {"query": "(image)", "shots": [
        {"video_id": vid, "original_filename": f"{vid}.mp4", "t_start": 12.0, "t_end": 15.0, "score": 0.83}]}


def fo_concepts(name):
    return {"kg_available": True, "concepts": [
        {"entity_id": "e1", "canonical_name": name, "entity_type": "concept",
         "score": 0.8, "mention_count": 5, "video_count": 2}]}


def fo_mentions(name, vid):
    return {"resolved_concept": {"entity_id": "e2", "canonical_name": name},
            "mentions": [{"video_id": vid, "video_title": "Lecture", "video_position": 3,
                          "t_start": 200.0, "t_end": 230.0, "transcript": f"discussing {name}"}]}


def fo_relations(name):
    return {"resolved_concept": {"entity_id": "e1", "canonical_name": name},
            "related": [{"entity_id": "e3", "canonical_name": "related concept",
                         "relation": "is related to", "weight": 0.7, "direction": "outgoing"}]}


def fo_sounds(tag, vid):
    return {"video_id": vid, "shots": [
        {"idx": 9, "t_start": 66.0, "t_end": 70.0, "audio_tags": [{"label": tag, "confidence": 0.82}]}]}


def fo_similar(vid):
    return {"video_id": vid, "results": [
        {"video_id": f"{vid}-sim", "original_filename": "similar.mp4", "duration_s": 90.0,
         "shot_count": 12, "score": 0.76}]}


def fo_qa(vid, ans):
    return {"video_id": vid, "answer": ans, "citations": [{"t_start": 10.0, "t_end": 14.0}], "modality": "video"}


def fo_sequence():
    return {"ordered": True, "steps": ["a", "b", "c"], "per_step": [
        {"step": "a", "t_start": 5.0, "t_end": 9.0}, {"step": "b", "t_start": 20.0, "t_end": 24.0},
        {"step": "c", "t_start": 40.0, "t_end": 44.0}]}


def fo_edit(vid):
    return {"video_id": vid, "output_url": "s3://edits/out.mp4", "clips": [{"t_start": 10.0, "t_end": 20.0}]}


def fo_moderate(vid):
    return {"video_id": vid, "flagged_shots": [], "per_shot_nsfw": [{"idx": 0, "nsfw": 0.02}]}


goldens: dict[str, list] = {}

# ---------------- search_corpus (text -> video corpus, group_by video) ----------------
_corpus = [
    ("find videos about basketball", "basketball"),
    ("show me cooking videos", "cooking"),
    ("which of my videos are about machine learning?", "machine learning"),
    ("do I have any nature documentaries?", "nature documentary"),
    ("find footage of a soccer match", "soccer match"),
    ("look for videos discussing climate change", "climate change"),
    ("any videos with live concert performances?", "live concert"),
    ("search my library for tennis matches", "tennis match"),
    ("find videos about python programming", "python programming"),
]
goldens["search_corpus"] = [
    case(f"corpus-{i}", q, "search_corpus", {"query": f"~{t}", "group_by": "video"},
         fo_shots(t, group="video"))
    for i, (q, t) in enumerate(_corpus)
]

# ---------------- search_video_local (within one pinned video) ----------------
_local = [
    ("find the part of this video where they discuss defense", "defense", "bball"),
    ("where in this video do they mention the recipe ingredients?", "ingredients", "cook"),
    ("jump to the section about gradient descent in this video", "gradient descent", "ml"),
    ("locate the moment they talk about the final score", "final score", "soccer"),
    ("find where the guitar solo is explained in this video", "guitar solo", "concert"),
    ("which part of this video covers the serve technique?", "serve technique", "tennis"),
]
goldens["search_video_local"] = [
    case(f"local-{i}", q, "search_video_local", {"video_id": V[v], "query": f"~{t}"},
         fo_local(t, V[v]), context={"video_id": V[v]})
    for i, (q, t, v) in enumerate(_local)
]

# ---------------- search_motion (action/motion -> video) ----------------
_motion = [
    ("find clips of someone dunking a basketball", "dunk"),
    ("show me people running fast", "running"),
    ("find moments where someone is dancing", "dancing"),
    ("clips of a car drifting", "car drifting"),
    ("find footage of someone jumping", "jumping"),
    ("show me a person flipping a pancake", "flipping pancake"),
]
goldens["search_motion"] = [
    case(f"motion-{i}", q, "search_motion", {"query": f"~{t}", "group_by": "video"},
         fo_shots(t, group="video"))
    for i, (q, t) in enumerate(_motion)
]

# ---------------- search_index (text within an Index / course) ----------------
_index = [
    ("which lecture in this course covers gradient descent?", "gradient descent", "ml"),
    ("which video in this course is about overfitting?", "overfitting", "ml"),
    ("find the lecture that introduces backpropagation", "backpropagation", "ml"),
    ("which video shows how to make pasta dough?", "pasta dough", "cook"),
    ("which lecture covers the French Revolution?", "French Revolution", "hist"),
    ("find the video segment about regularization in this course", "regularization", "ml"),
    ("which video teaches knife skills?", "knife skills", "cook"),
]
goldens["search_index"] = [
    case(f"index-{i}", q, "search_index", {"index_id": IDX[ix], "query": f"~{t}"},
         fo_shots(t, vid=f"vid-{ix}-3"), context={"index_id": IDX[ix], "video_ids": []})
    for i, (q, t, ix) in enumerate(_index)
]

# ---------------- ground_video ("when does X happen" -> timestamps) ----------------
_ground = [
    ("when does the goal happen in this video?", "goal", "soccer"),
    ("at what point do they add the tomato sauce?", "add tomato sauce", "cook"),
    ("when does the player score the winning point?", "winning point", "tennis"),
    ("find the moment the guitar solo starts", "guitar solo starts", "concert"),
    ("when do they introduce the main theorem?", "main theorem", "ml"),
    ("at what timestamp does the explosion occur?", "explosion", "news"),
    ("when does the dunk happen?", "dunk", "bball"),
    ("find when the chef starts plating the dish", "plating the dish", "cook2"),
    ("when does the sunset appear in this video?", "sunset", "nature"),
]
goldens["ground_video"] = [
    case(f"ground-{i}", q, "ground_video", {"video_id": V[v], "query": f"~{t}"},
         fo_moments(t, V[v]), context={"video_id": V[v]})
    for i, (q, t, v) in enumerate(_ground)
]

# ---------------- get_highlights ----------------
_high = [
    ("give me the highlights of this video", "soccer"),
    ("make a highlight reel for this match", "bball"),
    ("what are the best moments in this video?", "concert"),
    ("show me the key moments", "tennis"),
    ("summarize this into a highlight clip", "news"),
    ("pull the exciting parts of this video", "nature"),
]
goldens["get_highlights"] = [
    case(f"high-{i}", q, "get_highlights", {"video_id": V[v]}, fo_highlights(V[v]),
         context={"video_id": V[v]})
    for i, (q, v) in enumerate(_high)
]

# ---------------- find_scene_by_image (image attached + single video) ----------------
_scene_local = [
    ("where in this video does this frame appear?", "bball"),
    ("find the moment that matches this image in this video", "cook"),
    ("locate this scene within this video", "soccer"),
    ("at what time does this shot occur in this video?", "concert"),
    ("find where this picture is from in this video", "nature"),
    ("which timestamp in this video matches this image?", "tennis"),
]
goldens["find_scene_by_image"] = [
    case(f"sceneL-{i}", q, "find_scene_by_image", {"video_id": V[v]}, fo_scene_local(V[v]),
         context={"video_id": V[v], "image": "data:image/png;base64,FAKE"})
    for i, (q, v) in enumerate(_scene_local)
]

# ---------------- search_scene_by_image (image attached, corpus-wide) ----------------
_scene_corpus = [
    ("which video is this scene from?", "bball"),
    ("find which of my videos this image came from", "cook"),
    ("what video does this frame belong to?", "soccer"),
    ("search all my videos for this scene", "nature"),
    ("identify the video this picture is taken from", "concert"),
    ("where across my library does this image appear?", "tennis"),
]
goldens["search_scene_by_image"] = [
    case(f"sceneC-{i}", q, "search_scene_by_image", {}, fo_scene_corpus(V[v]),
         context={"image": "data:image/png;base64,FAKE"})
    for i, (q, v) in enumerate(_scene_corpus)
]

# ---------------- find_index_concepts (KG entity search) ----------------
_concepts = [
    ("what key concepts are covered in this course?", "concepts", "ml"),
    ("list the main topics in this lecture series", "topics", "ml"),
    ("what techniques does this cooking course teach?", "techniques", "cook"),
    ("what are the important ideas in this course?", "ideas", "hist"),
    ("show me the core concepts of this course", "core concepts", "ml"),
    ("what subjects are taught in this course?", "subjects", "cook"),
]
goldens["find_index_concepts"] = [
    case(f"kgc-{i}", q, "find_index_concepts", {"index_id": IDX[ix], "topic": f"~{t}"},
         fo_concepts(t), context={"index_id": IDX[ix], "video_ids": []})
    for i, (q, t, ix) in enumerate(_concepts)
]

# ---------------- find_concept_mentions (where is X discussed) ----------------
_mentions = [
    ("where is backpropagation discussed in this course?", "backpropagation", "ml"),
    ("which lectures mention the chain rule?", "chain rule", "ml"),
    ("where in this course do they talk about emulsification?", "emulsification", "cook"),
    ("find all the places that discuss the Cold War", "Cold War", "hist"),
    ("where is the learning rate explained?", "learning rate", "ml"),
    ("which segments mention caramelization?", "caramelization", "cook"),
]
goldens["find_concept_mentions"] = [
    case(f"kgm-{i}", q, "find_concept_mentions", {"index_id": IDX[ix], "concept_name": f"~{t}"},
         fo_mentions(t, f"vid-{ix}-4"), context={"index_id": IDX[ix], "video_ids": []})
    for i, (q, t, ix) in enumerate(_mentions)
]

# ---------------- find_concept_relations (what relates to X) ----------------
_relations = [
    ("what concepts are related to gradient descent in this course?", "gradient descent", "ml"),
    ("what is backpropagation connected to?", "backpropagation", "ml"),
    ("what prerequisites does overfitting relate to?", "overfitting", "ml"),
    ("what techniques are related to braising in this course?", "braising", "cook"),
    ("how does the French Revolution connect to other topics here?", "French Revolution", "hist"),
    ("what is the learning rate associated with?", "learning rate", "ml"),
]
goldens["find_concept_relations"] = [
    case(f"kgr-{i}", q, "find_concept_relations", {"index_id": IDX[ix], "concept_name": f"~{t}"},
         fo_relations(t), context={"index_id": IDX[ix], "video_ids": []})
    for i, (q, t, ix) in enumerate(_relations)
]

# ---------------- find_sounds (audio event filter) ----------------
_sounds = [
    ("find the moments with applause in this video", "Applause", "concert"),
    ("where is there laughter in this video?", "Laughter", "news"),
    ("find parts of this video with music playing", "Music", "concert"),
    ("locate the cheering in this video", "Cheering", "soccer"),
    ("when can I hear a whistle in this video?", "Whistle", "tennis"),
    ("find sections with a dog barking", "Dog", "nature"),
]
goldens["find_sounds"] = [
    case(f"sound-{i}", q, "find_sounds", {"video_id": V[v], "tag": f"~{t}"}, fo_sounds(t, V[v]),
         context={"video_id": V[v]})
    for i, (q, t, v) in enumerate(_sounds)
]

# ---------------- find_similar (video -> similar videos) ----------------
_similar = [
    ("find videos similar to this one", "bball"),
    ("show me more videos like this", "cook"),
    ("what else do I have that's similar to this video?", "soccer"),
    ("find related videos to this one", "concert"),
    ("recommend videos like this", "nature"),
    ("which of my videos resemble this one?", "tennis"),
]
goldens["find_similar"] = [
    case(f"sim-{i}", q, "find_similar", {"video_id": V[v]}, fo_similar(V[v]),
         context={"video_id": V[v]})
    for i, (q, v) in enumerate(_similar)
]

# ---------------- ask_video_local (free-form QA / summary on one video) ----------------
_qa = [
    ("summarize this video", "bball", "This video shows a basketball game."),
    ("what is this video about?", "cook", "It is a cooking tutorial."),
    ("explain what happens in this video", "soccer", "A soccer match with a late goal."),
    ("who is the main person in this video?", "news", "A news anchor presents a report."),
    ("give me a short description of this video", "nature", "A nature documentary about wildlife."),
    ("what's the takeaway from this video?", "tut", "A tutorial explaining a process."),
]
goldens["ask_video_local"] = [
    case(f"qa-{i}", q, "ask_video_local", {"video_id": V[v], "question": f"~{q}"}, fo_qa(V[v], ans),
         context={"video_id": V[v]}, reference=ans)
    for i, (q, v, ans) in enumerate(_qa)
]

# ---------------- find_sequence (compositional A->B->C ordering) ----------------
_seq = [
    ("does he chop the onions before adding the garlic in this video?", "cook"),
    ("verify that the player dribbles then shoots in this clip", "bball"),
    ("check whether they explain the theory before the example", "ml"),
    ("did the goal happen after the foul in this match?", "soccer"),
]
goldens["find_sequence"] = [
    case(f"seq-{i}", q, "find_sequence", {"video_id": V[v]}, fo_sequence(),
         context={"video_id": V[v]})
    for i, (q, v) in enumerate(_seq)
]

# ---------------- combine_clips (editing) ----------------
_edit = [
    ("cut the first 10 seconds and the goal moment into one clip", "soccer"),
    ("combine the dunk and the celebration into a single video", "bball"),
    ("stitch together the intro and the recipe steps", "cook"),
]
goldens["combine_clips"] = [
    case(f"edit-{i}", q, "combine_clips", {"video_id": V[v]}, fo_edit(V[v]),
         context={"video_id": V[v]})
    for i, (q, v) in enumerate(_edit)
]

# ---------------- moderate_video (NSFW / toxicity) ----------------
_mod = [
    ("is there any inappropriate content in this video?", "news"),
    ("check this video for NSFW material", "concert"),
    ("does this video contain anything unsafe or toxic?", "tut"),
]
goldens["moderate_video"] = [
    case(f"mod-{i}", q, "moderate_video", {"video_id": V[v]}, fo_moderate(V[v]),
         context={"video_id": V[v]})
    for i, (q, v) in enumerate(_mod)
]

# ---------------- disambiguation / adversarial (kept distinct ids) ----------------
goldens["disambiguation"] = [
    case("disambig-when-not-search", "when do they score in this game?", "ground_video",
         {"video_id": V["soccer"], "query": "~score"}, fo_moments("score", V["soccer"]),
         context={"video_id": V["soccer"]}),
    case("disambig-relations-not-mentions", "what is gradient descent connected to?",
         "find_concept_relations", {"index_id": IDX["ml"], "concept_name": "~gradient descent"},
         fo_relations("gradient descent"), context={"index_id": IDX["ml"], "video_ids": []}),
    case("disambig-mentions-not-relations", "where is gradient descent actually discussed?",
         "find_concept_mentions", {"index_id": IDX["ml"], "concept_name": "~gradient descent"},
         fo_mentions("gradient descent", "vid-ml-4"), context={"index_id": IDX["ml"], "video_ids": []}),
    case("disambig-stale-video-scope", "summarize this video", "ask_video_local",
         {"video_id": V["newattach"], "question": "~summarize"},
         fo_qa(V["newattach"], "This video shows a basketball game."),
         context={"video_id": V["newattach"]}, reference="This video shows a basketball game."),
    case("disambig-image-corpus-not-text", "which video is this scene from?", "search_scene_by_image",
         {}, fo_scene_corpus(V["bball"]), context={"image": "data:image/png;base64,FAKE"}),
    case("disambig-local-not-corpus", "where in THIS video do they talk about defense?",
         "search_video_local", {"video_id": V["bball"], "query": "~defense"},
         fo_local("defense", V["bball"]), context={"video_id": V["bball"]}),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.yaml"):
        old.unlink()
    total = 0
    for family, cases in goldens.items():
        (OUT / f"{family}.yaml").write_text(
            yaml.safe_dump(cases, sort_keys=False, allow_unicode=True, width=120)
        )
        total += len(cases)
    print(f"wrote {total} goldens across {len(goldens)} files into {OUT}")


if __name__ == "__main__":
    main()

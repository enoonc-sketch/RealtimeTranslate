"""造一个随机权重的 Argos 兼容语言包（仅用于测试推理链路，译文是乱码）。"""
import json, os, sys, tempfile, shutil
import numpy as np
import sentencepiece as spm
import ctranslate2
from ctranslate2.specs import TransformerSpec

def make_pkg(root, from_code, to_code, corpus_lines, target_prefix="", seed=0):
    rng = np.random.default_rng(seed)
    name = "translate-%s_%s-1_0" % (from_code, to_code)
    pkg = os.path.join(root, name)
    os.makedirs(os.path.join(pkg, "model"), exist_ok=True)
    # 1. sentencepiece
    tmp = tempfile.mkdtemp()
    cp = os.path.join(tmp, "c.txt")
    open(cp, "w", encoding="utf-8").write("\n".join(corpus_lines))
    spm.SentencePieceTrainer.train(input=cp, model_prefix=os.path.join(tmp, "sp"),
                                   vocab_size=60, hard_vocab_limit=False, model_type="unigram",
                                   character_coverage=1.0)
    shutil.copy(os.path.join(tmp, "sp.model"), os.path.join(pkg, "sentencepiece.model"))
    sp = spm.SentencePieceProcessor(model_file=os.path.join(tmp, "sp.model"))
    vocab = [sp.id_to_piece(i) for i in range(sp.vocab_size())]
    V, D, F, H = len(vocab), 16, 32, 2
    # 2. ctranslate2 model
    spec = TransformerSpec.from_config(num_layers=1, num_heads=H)
    def fill(name):
        r = lambda *s: rng.standard_normal(s).astype(np.float32) * 0.1
        if "embeddings" in name: return r(V, D)
        if "layer_norm/gamma" in name: return np.ones(D, np.float32)
        if "layer_norm/beta" in name: return np.zeros(D, np.float32)
        if name.startswith("decoder/projection"):
            return r(V, D) if name.endswith("weight") else np.zeros(V, np.float32)
        parts = name.split("/")
        kind = parts[-1]
        if "self_attention/linear_0" in name: out, inn = 3 * D, D
        elif "self_attention/linear_1" in name: out, inn = D, D
        elif "attention/linear_0" in name: out, inn = D, D        # cross: q
        elif "attention/linear_1" in name: out, inn = 2 * D, D    # cross: kv
        elif "attention/linear_2" in name: out, inn = D, D
        elif "ffn/linear_0" in name: out, inn = F, D
        elif "ffn/linear_1" in name: out, inn = D, F
        else: raise KeyError(name)
        return r(out, inn) if kind == "weight" else np.zeros(out, np.float32)
    missing = [k for k, v in spec.variables().items() if v is None]
    for k in missing:
        obj = spec
        *path, leaf = k.split("/")
        for p in path:
            base, _, idx = p.rpartition("_")
            if not hasattr(obj, p) and idx.isdigit():
                obj = getattr(obj, base)[int(idx)]
            else:
                obj = getattr(obj, p)
        setattr(obj, leaf, fill(k))
    spec.register_source_vocabulary(vocab)
    spec.register_target_vocabulary(vocab)
    spec.validate()
    spec.save(os.path.join(pkg, "model"))
    meta = {"package_version": "1.0", "argos_version": "1.9", "from_code": from_code, "from_name": from_code,
            "to_code": to_code, "to_name": to_code, "code": "%s_%s" % (from_code, to_code),
            "target_prefix": target_prefix, "type": "translate"}
    json.dump(meta, open(os.path.join(pkg, "metadata.json"), "w"))
    return pkg

if __name__ == "__main__":
    root = sys.argv[1]
    en = ["hello world this is a test", "how are you today", "the quick brown fox jumps", "good morning everyone"] * 5
    zh = ["你好世界这是一个测试", "你今天好吗", "快速的棕色狐狸跳跃", "大家早上好"] * 5
    print(make_pkg(root, "en", "zh", en + zh))
    print(make_pkg(root, "zh", "en", zh + en, seed=1))

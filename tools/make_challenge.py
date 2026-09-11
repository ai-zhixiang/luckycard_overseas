#!/usr/bin/env python3
"""make_challenge.py — 一键生成新挑战(站长用, 不是网站的一部分)。

用法:
  # 经典算法题 (自己填密文和明文):
  python3 tools/make_challenge.py --qid Q9 --algo "Rail fence cipher" \
      --hint "Write it out in rows, then read it differently." \
      --pts 25 --answer "the plains" --cipher "te lhpains"

  # boon-enc 套娃题 (明文 + 轮数 + 种子, 脚本生成密文):
  python3 tools/make_challenge.py --qid Q10 --rounds 12 --seed 20261001 \
      --answer "your secret phrase" --pts 25

输出: 直接打好补丁的 JSON 片段 → 追加到 app/data/crypto_challenges.json 的数组里。
答案只写 SHA-256, 明文不落盘。

⚠️ 出完题务必自检: 每题 hint/algo 里出现的词组不能等于答案
   (Q8 曾把答案 the final boss 写进 hint, 白送 100 分)。
   本脚本会自动跑这个检查, 有问题直接报错。
"""
import argparse
import base64
import hashlib
import json
import random
import sys

CHALL_FILE = "app/data/crypto_challenges.json"


# ── boon-enc v1 复刻 (与站长算法一致: 只可逆变换套娃) ──
def _to_ascii(s: str) -> str:
    return "".join(str(ord(c)) for c in s)


def _from_ascii(s: str) -> str:
    # ascii 数字流无分隔符 → 3 位一组 (仅适用于码点 < 1000 的字符)
    out = ""
    for i in range(0, len(s), 3):
        out += chr(int(s[i:i + 3]))
    return out


def _rot(s: str, n: int) -> str:
    out = []
    for c in s:
        if "a" <= c <= "z":
            out.append(chr((ord(c) - 97 + n) % 26 + 97))
        elif "A" <= c <= "Z":
            out.append(chr((ord(c) - 65 + n) % 26 + 65))
        else:
            out.append(c)
    return "".join(out)


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode()


def _unb64(s: str) -> str:
    return base64.b64decode(s.encode("utf-8")).decode("utf-8")


def _func(s: str) -> str:
    """标记性变换: 反转 + 包一层括号 (解密时剥掉)。"""
    return "(" + s[::-1] + ")"


def _unfunc(s: str) -> str:
    return s[1:-1][::-1]


def boon_enc_rounds(text: str, rounds: int, seed: int) -> tuple[str, list]:
    """返回 (密文, 变换序列)。序列是站长密钥, 不要公开。"""
    rng = random.Random(seed)
    recipe = []
    cur = text
    for _ in range(rounds):
        pick = rng.choice(["ascii", "base64", "func", "rot"])
        if pick == "ascii":
            cur = _to_ascii(cur)
        elif pick == "base64":
            cur = _b64(cur)
        elif pick == "func":
            cur = _func(cur)
        else:
            n = rng.randint(3, 25)
            recipe.append(("rot", n))
            cur = _rot(cur, n)
            continue
        recipe.append((pick,))
    return cur, recipe


def decrypt_rounds(cipher: str, recipe: list) -> str:
    cur = cipher
    for step in reversed(recipe):
        if step[0] == "ascii":
            cur = _from_ascii(cur)
        elif step[0] == "base64":
            cur = _unb64(cur)
        elif step[0] == "func":
            cur = _unfunc(cur)
        elif step[0] == "rot":
            cur = _rot(cur, -step[1])
    return cur


def self_check(qid, algo, hint, answer, cipher) -> None:
    norm = answer.strip().lower()
    for field, val in (("hint", hint), ("algo", algo), ("qid", qid)):
        if val and norm in val.strip().lower():
            sys.exit(f"❌ {field} 里含答案原文 '{answer}' — 白送分, 改掉再出题")
    if cipher and norm in cipher.lower():
        sys.exit("❌ 密文里直接含答案 — 这题废了")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qid", required=True)
    ap.add_argument("--algo", default="boon-enc v1 (nested rounds)")
    ap.add_argument("--hint", default="Peel it like an onion, from the outside in.")
    ap.add_argument("--pts", type=int, default=25)
    ap.add_argument("--diff", type=int, default=2)
    ap.add_argument("--answer", required=True, help="明文答案 (只用来算 hash, 不落盘)")
    ap.add_argument("--cipher", default=None, help="经典算法题: 直接给密文")
    ap.add_argument("--rounds", type=int, default=None, help="boon-enc: 套娃轮数")
    ap.add_argument("--seed", type=int, default=None, help="boon-enc: 固定种子")
    ap.add_argument("--file", default=None, help="密文放文件时的下载路径")
    ap.add_argument("--write-file", default=None, help="把生成的密文写到这个路径")
    a = ap.parse_args()

    cipher = a.cipher
    recipe = None
    if a.rounds:
        if a.seed is None:
            sys.exit("❌ boon-enc 题必须给 --seed (固定种子才能复现你自己的破解)")
        cipher, recipe = boon_enc_rounds(a.answer, a.rounds, a.seed)
        assert decrypt_rounds(cipher, recipe) == a.answer, "自检失败: 解不回去"
        if a.write_file:
            with open(a.write_file, "w", encoding="utf-8") as f:
                f.write(cipher)
            print(f"密文已写入 {a.write_file} ({len(cipher)} 字符)")
            a.file = "/static/challenges/" + a.write_file.split("/")[-1]
            cipher = None
    if not cipher and not a.file:
        sys.exit("❌ 要给 --cipher (直接密文) 或 --rounds (boon-enc) 之一")

    self_check(a.qid, a.algo, a.hint, a.answer, cipher or "")

    entry = {
        "qid": a.qid,
        "diff": a.diff,
        "algo": a.algo,
        "hint": a.hint,
        "pts": a.pts,
        "sha256": hashlib.sha256(a.answer.strip().lower().encode()).hexdigest(),
    }
    if cipher:
        entry["cipher"] = cipher
    if a.file:
        entry["file"] = a.file

    print("\n=== 追加到 " + CHALL_FILE + " 数组里 ===\n")
    print(json.dumps(entry, ensure_ascii=False, indent=1) + ",")
    if recipe:
        print("\n=== 站长密钥: 变换序列 (自己存好, 别公开) ===")
        print(json.dumps(recipe, ensure_ascii=False))
    print("\n答案哈希已生成。明文没有写进任何文件。")


if __name__ == "__main__":
    main()

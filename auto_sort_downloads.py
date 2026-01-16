import re
import time
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Dict, List

import whisper

DOWNLOADS_DIR = Path.home() / "Downloads"
PROJECT_DIR = Path(__file__).resolve().parent
INPUT_DIR = PROJECT_DIR / "input_videos"

CATEGORIES = {
    "pregacao": INPUT_DIR / "pregacao",
    "desenvolvimento_pessoal": INPUT_DIR / "desenvolvimento_pessoal",
    "revisar": INPUT_DIR / "revisar",
}

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}

# ⚡ pra classificar, usa tiny (bem mais rápido)
WHISPER_MODEL = "tiny"

# checagem
CHECK_EVERY_SECONDS = 6

# ⚡ preview rápido (bem mais rápido que transcrever tudo)
PREVIEW_SECONDS = 45
PREVIEW_OFFSET_SECONDS = 30
TMP_DIR = PROJECT_DIR / "_tmp_previews"

# heurística
MIN_DIFF_TO_DECIDE = 3
MIN_SCORE_TO_DECIDE = 4

KEYWORDS = {
    "pregacao": [
        "deus", "jesus", "cristo", "espírito santo", "espirito santo", "fé", "fe",
        "oração", "oracao", "bênção", "bencao", "pecado", "arrependimento",
        "salvação", "salvacao", "evangelho", "bíblia", "biblia", "pastor", "igreja",
        "glória", "gloria", "senhor", "amém", "amen", "milagre", "profecia"
    ],
    "desenvolvimento_pessoal": [
        "disciplina", "foco", "mindset", "hábitos", "habitos", "rotina",
        "constância", "constancia", "produtividade", "procrastinação", "procrastinacao",
        "metas", "objetivo", "evolução", "evolucao", "autocontrole", "motivação",
        "motivacao", "resiliência", "resiliencia", "autoestima", "crescimento",
        "carreira", "trabalho", "dinheiro", "performance"
    ]
}

def ensure_dirs():
    for p in CATEGORIES.values():
        p.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

def normalize_text(t: str) -> str:
    t = (t or "").lower()
    t = re.sub(r"\s+", " ", t)
    return t

def score_category(text: str, category: str) -> int:
    t = normalize_text(text)
    score = 0
    for kw in KEYWORDS[category]:
        if kw in t:
            score += 1
    return score

def classify_transcript(text: str) -> Tuple[str, Dict[str, int]]:
    scores = {cat: score_category(text, cat) for cat in ["pregacao", "desenvolvimento_pessoal"]}
    winner = max(scores, key=scores.get)
    loser = "pregacao" if winner == "desenvolvimento_pessoal" else "desenvolvimento_pessoal"

    if scores[winner] >= MIN_SCORE_TO_DECIDE and (scores[winner] - scores[loser]) >= MIN_DIFF_TO_DECIDE:
        return winner, scores

    return "revisar", scores

def run(cmd: List[str]):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def make_preview_clip(video_path: Path) -> Path:
    out = TMP_DIR / f"{video_path.stem}__preview.mp4"
    if out.exists():
        out.unlink(missing_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(PREVIEW_OFFSET_SECONDS),
        "-i", str(video_path),
        "-t", str(PREVIEW_SECONDS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        str(out)
    ]
    run(cmd)
    return out

def transcribe_video(model, video_path: Path) -> str:
    preview = make_preview_clip(video_path)
    try:
        result = model.transcribe(
            str(preview),
            fp16=False,
            language="pt"
        )
        return result.get("text", "") or ""
    finally:
        preview.unlink(missing_ok=True)

def move_to_category(src: Path, category: str):
    dest_dir = CATEGORIES[category]
    dest = dest_dir / src.name

    if dest.exists():
        stem = src.stem
        suffix = src.suffix
        i = 2
        while True:
            candidate = dest_dir / f"{stem}_{i}{suffix}"
            if not candidate.exists():
                dest = candidate
                break
            i += 1

    shutil.move(str(src), str(dest))
    print(f"✅ Movido: {src.name}  ->  {category}/ ({dest.name})")

def scan_downloads_for_videos() -> List[Path]:
    files = []
    for p in DOWNLOADS_DIR.iterdir():
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            if p.name.endswith(".part") or p.name.endswith(".crdownload"):
                continue
            files.append(p)
    return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)

def main():
    ensure_dirs()
    print(f"📥 Monitorando: {DOWNLOADS_DIR}")
    print(f"📦 Enviando para: {INPUT_DIR}")
    print(f"⚙️ Carregando Whisper ({WHISPER_MODEL})...")
    model = whisper.load_model(WHISPER_MODEL)

    last_sizes: Dict[str, int] = {}
    stable_hits: Dict[str, int] = {}
    processed = set()

    while True:
        try:
            videos = scan_downloads_for_videos()

            for vid in videos:
                try:
                    st = vid.stat()
                except FileNotFoundError:
                    continue

                # chave por nome + size + mtime (pra não repetir)
                key = f"{vid.name}|{st.st_size}|{int(st.st_mtime)}"
                if key in processed:
                    continue

                # estabilidade: size repetido 2 ciclos seguidos
                prev = last_sizes.get(str(vid))
                if prev == st.st_size and st.st_size > 0:
                    stable_hits[str(vid)] = stable_hits.get(str(vid), 0) + 1
                else:
                    stable_hits[str(vid)] = 0
                last_sizes[str(vid)] = st.st_size

                if stable_hits[str(vid)] < 2:
                    continue

                print(f"\n🔍 Classificando: {vid.name}")

                try:
                    transcript = transcribe_video(model, vid)
                    category, scores = classify_transcript(transcript)
                    print(f"📊 Scores: {scores} -> destino: {category}")

                    if vid.exists():
                        move_to_category(vid, category)

                    processed.add(key)

                except Exception as e:
                    print(f"⚠️ Falhou ao processar {vid.name}: {e}")
                    processed.add(key)

            time.sleep(CHECK_EVERY_SECONDS)

        except KeyboardInterrupt:
            print("\n👋 Parando monitoramento.")
            break

if __name__ == "__main__":
    main()

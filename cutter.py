from __future__ import annotations

import re
import subprocess
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from collections import Counter

from dateutil.tz import gettz
import whisper

# =============================
# DATA CLASS (CORREÇÃO ✅)
# =============================
@dataclass
class Seg:
    start: float
    end: float
    text: str
    score: float


# =============================
# CONFIG
# =============================
TIMEZONE = "America/Sao_Paulo"

INPUT_DIR = "input_videos"
OUTPUT_DIR = "output"

# 5 posts por dia
POST_TIMES = ["06:00", "06:30", "10:00", "10:30", "04:30"]

# Cortes
CLIP_MIN_SECONDS = 60
CLIP_MAX_SECONDS = 180          # pode passar de 90 (180=3min) -> altere se quiser
MAX_CLIPS_PER_VIDEO = 10         # máximo por vídeo

WHISPER_MODEL = "base"

# TikTok 9:16
TIKTOK_WIDTH = 1080
TIKTOK_HEIGHT = 1920
TIKTOK_MODE = "BLUR"            # "BLUR" recomendado pra YouTube 16:9, "CROP" pra tela cheia

# Legendas embutidas
BURN_CAPTIONS_IN_VIDEO = True
CAPTION_FONT_NAME = "TikTokSans-VariableFont"  # nome do arquivo/família que você usa no ASS
CAPTION_FONT_SIZE = 56
CAPTION_MARGIN_V = 170
KEEP_DEBUG_FILES = False

# Paleta fallback
FALLBACK_ACCENTS = ["#00E5FF", "#FF3D71", "#FFD300", "#9B59FF", "#00D68F", "#FF6B00"]

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}

# =============================
# NLP / hashtags
# =============================
STOPWORDS_PT = {
    "a","o","os","as","um","uma","uns","umas","de","do","da","dos","das",
    "em","no","na","nos","nas","pra","para","por","com","sem","que","e","é",
    "ser","ter","foi","vai","tá","ta","eu","vc","você","voce","vocês","me","te",
    "se","não","nao","sim","mais","menos","muito","muita","muitos","muitas",
    "isso","essa","esse","aqui","ali","lá","la","já","ja","também","tambem",
    "porque","quando","como","onde","quem","tudo","todo","toda","todos","todas",
    "nós","nos","nosso","minha","meu","seu","sua","dele","dela","eles","elas",
    "só","so"
}

HASHTAG_POOLS = {
    "pregacao": [
        "#pregacao","#palavradedeus","#fe","#jesus","#deus","#evangelho","#biblia",
        "#oracao","#adoracao","#proposito","#restauracao","#cura","#milagre","#graca",
        "#perdao","#esperanca","#promessa","#espiritosanto","#cristao","#igreja",
        "#devocional","#mensagem","#palavra","#reflexao","#salvacao","#amor","#familia",
        "#ansiedade","#medo","#confiancaemdeus"
    ],
    "desenvolvimento_pessoal": [
        "#desenvolvimentopessoal","#mindset","#disciplina","#foco","#evolucao","#habitos",
        "#rotina","#produtividade","#metas","#consistencia","#motivacao","#autoconhecimento",
        "#autocontrole","#crescimento","#carreira","#trabalho","#performance","#gestaodotempo",
        "#procrastinacao","#resiliencia","#mentalidade","#sucesso","#aprendizado",
        "#empreendedorismo","#dinheiro","#objetivos","#autoconfianca","#lideranca","#persistencia"
    ],
    "revisar": ["#viral","#tiktokbr","#foryou","#paravoce","#cortes","#reels","#shorts","#trend","#podcast","#conteudo"],
}

KEYWORD_HASHTAG_MAP = {
    # pregacao
    "proposito":"#proposito","propósito":"#proposito","fe":"#fe","fé":"#fe",
    "oracao":"#oracao","oração":"#oracao","graca":"#graca","graça":"#graca",
    "perdao":"#perdao","perdão":"#perdao","salvacao":"#salvacao","salvação":"#salvacao",
    "familia":"#familia","família":"#familia","ansiedade":"#ansiedade","medo":"#medo",
    "espera":"#espera","promessa":"#promessa",
    # dev pessoal
    "habito":"#habitos","hábito":"#habitos","rotina":"#rotina","consistencia":"#consistencia",
    "consistência":"#consistencia","meta":"#metas","foco":"#foco","disciplina":"#disciplina",
    "produtividade":"#produtividade","autocontrole":"#autocontrole","procrastinacao":"#procrastinacao",
    "procrastinação":"#procrastinacao","dinheiro":"#dinheiro","trabalho":"#trabalho",
}

USED_HASHTAGS = set()

# =============================
# Viral scoring (heurística)
# =============================
VIRAL_TRIGGERS = [
    "ninguém","segredo","erro","presta atenção","a real","o problema",
    "sabe por quê","sabe por que","não faça","nao faca","faz isso","do jeito certo","muda tudo",
]
NUMBER_PATTERN = re.compile(r"\b(\d+|um|dois|tres|três|quatro|cinco|dez|%|r\$)\b", re.IGNORECASE)


def run(cmd: List[str]):
    subprocess.run(cmd, check=True)


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def _normalize_word(w: str) -> str:
    w = w.lower().strip()
    w = re.sub(r"[^\wáàâãéèêíìîóòôõúùûç]+", "", w, flags=re.IGNORECASE)
    return w


def extract_keywords(text: str, top_n: int = 6) -> List[str]:
    words = [_normalize_word(w) for w in (text or "").split()]
    words = [w for w in words if w and len(w) >= 4 and w not in STOPWORDS_PT]
    if not words:
        return []
    counts = Counter(words)
    return [w for w, _ in counts.most_common(top_n)]


def build_hashtags(category: str, keywords: List[str], seed_text: str) -> List[str]:
    pool = HASHTAG_POOLS.get(category, HASHTAG_POOLS["revisar"]).copy()
    rnd = random.Random(abs(hash(seed_text)) % (2**32))

    themed = []
    for k in keywords:
        tag = KEYWORD_HASHTAG_MAP.get(k)
        if tag and tag not in themed:
            themed.append(tag)

    rnd.shuffle(themed)
    rnd.shuffle(pool)

    final = []

    # até 3 temáticas (quando houver)
    for t in themed[:3]:
        if len(final) >= 5:
            break
        if t not in final and t not in USED_HASHTAGS:
            final.append(t)

    # completa com pool sem repetir global
    for t in pool:
        if len(final) >= 5:
            break
        if t not in final and t not in USED_HASHTAGS:
            final.append(t)

    # fallback se ainda faltar
    for t in themed + pool:
        if len(final) >= 5:
            break
        if t not in final:
            final.append(t)

    for t in final:
        USED_HASHTAGS.add(t)

    return final[:5]


def make_caption_long(text: str, category: str, seed_text: str) -> str:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    kws = extract_keywords(raw, top_n=6)
    hashtags = build_hashtags(category, kws, seed_text=seed_text)
    tema = (kws[0] if kws else "isso").replace("_", " ")

    snippet = raw[:420].rstrip()
    if len(raw) > 420:
        snippet += "..."

    if category == "pregacao":
        hook = "Para tudo e ouve isso aqui."
        contexto = (
            f"Esse corte bate num ponto que muita gente tenta ignorar: **{tema}**.\n"
            f"Olha a essencia do que foi dito:\n“{snippet}”"
        )
        reflexao = (
            "Agora a reflexao que pega de verdade:\n"
            "Nem toda fase dificil e abandono — muitas vezes e direcao.\n"
            "Quando voce entende isso, voce para de viver no desespero e comeca a caminhar com fe.\n"
            "E fe nao e ausencia de medo… e continuar mesmo com o coracao tremendo."
        )
        cta = "Se isso falou com voce, comenta **AMEM**, salva pra reler e manda pra alguem que precisa."
    elif category == "desenvolvimento_pessoal":
        hook = "Isso aqui e um tapa necessario (com carinho)."
        contexto = (
            f"O tema do corte e **{tema}** — e isso mexe com tua rotina.\n"
            f"Resumo do que foi dito, sem enrolar:\n“{snippet}”"
        )
        reflexao = (
            "Reflexao aplicada (vida real):\n"
            "Voce nao precisa de um plano perfeito. Voce precisa de repeticao.\n"
            "Quem melhora 1% por dia, em alguns meses vira outra pessoa.\n"
            "A virada nao acontece no dia que voce se sente pronto — acontece no dia que voce comeca."
        )
        cta = "Se voce vai aplicar isso hoje, comenta **EU VOU**, salva e volta aqui mais tarde pra cumprir."
    else:
        hook = "Presta atencao nisso."
        contexto = f"Contexto do corte:\n“{snippet}”"
        reflexao = (
            "Reflexao:\n"
            "Ideia boa nao muda nada sozinha. Acao pequena e repetida muda tudo.\n"
            "Escolhe uma coisa pra aplicar hoje e executa."
        )
        cta = "Comenta **QUERO** e salva se isso te ajudou."

    return f"{hook}\n\n{contexto}\n\n{reflexao}\n\n{cta}\n{' '.join(hashtags)}"


def score_text(t: str) -> float:
    tl = (t or "").lower()
    score = 0.0
    for w in VIRAL_TRIGGERS:
        if w in tl:
            score += 2.0
    if NUMBER_PATTERN.search(tl):
        score += 2.0
    if "?" in t:
        score += 1.0
    words = len(t.split())
    if 6 <= words <= 18:
        score += 1.0
    if words > 35:
        score -= 0.5
    return score


# =============================
# TikTok 9:16 cut
# =============================
def ffmpeg_cut_tiktok(input_mp4: str, start_s: float, end_s: float, out_mp4: str):
    duration = max(0.1, end_s - start_s)

    if TIKTOK_MODE.upper() == "CROP":
        vf = (
            f"scale={TIKTOK_WIDTH}:{TIKTOK_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={TIKTOK_WIDTH}:{TIKTOK_HEIGHT},setsar=1"
        )
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start_s:.3f}",
            "-i", input_mp4,
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            out_mp4
        ]
    else:
        vf = (
            f"[0:v]scale={TIKTOK_WIDTH}:{TIKTOK_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={TIKTOK_WIDTH}:{TIKTOK_HEIGHT},gblur=sigma=20[bg];"
            f"[0:v]scale={TIKTOK_WIDTH}:{TIKTOK_HEIGHT}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start_s:.3f}",
            "-i", input_mp4,
            "-t", f"{duration:.3f}",
            "-filter_complex", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            out_mp4
        ]

    run(cmd)


# =============================
# Accent color from frame
# =============================
def extract_thumbnail(input_mp4: str, at_second: float, out_png: str):
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{at_second:.3f}",
        "-i", input_mp4,
        "-frames:v", "1",
        "-update", "1",
        out_png
    ]
    run(cmd)


def dominant_color_hex(png_path: str) -> Optional[str]:
    try:
        from PIL import Image
    except Exception:
        return None

    try:
        img = Image.open(png_path).convert("RGB").resize((96, 96))
        pixels = list(img.getdata())
        buckets: Dict[Tuple[int, int, int], int] = {}
        for r, g, b in pixels:
            key = (r // 16, g // 16, b // 16)
            buckets[key] = buckets.get(key, 0) + 1
        (qr, qg, qb), _ = max(buckets.items(), key=lambda x: x[1])
        r, g, b = qr * 16, qg * 16, qb * 16
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return None


def pick_accent_color(seed: str, thumb_png: Optional[str]) -> str:
    if thumb_png:
        c = dominant_color_hex(thumb_png)
        if c:
            return c
    return FALLBACK_ACCENTS[abs(hash(seed)) % len(FALLBACK_ACCENTS)]


# =============================
# ASS subtitles
# =============================
def hex_to_ass_bgr(hex_color: str, alpha_hex: str = "00") -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"&H{alpha_hex}{b:02X}{g:02X}{r:02X}"


def fmt_ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def escape_ass_text(text: str) -> str:
    text = text.replace("{", r"\{").replace("}", r"\}")
    return text


def write_ass_from_whisper_segments(
    whisper_segments: List[dict],
    clip_start: float,
    clip_end: float,
    ass_path: str,
    font_name: str,
    font_size: int,
    margin_v: int,
    primary_hex: str,
    outline_hex: str,
    highlight_hex: str,
):
    primary = hex_to_ass_bgr(primary_hex, "00")
    outline = hex_to_ass_bgr(outline_hex, "00")
    highlight = hex_to_ass_bgr(highlight_hex, "00")
    back = "&H80000000"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary},{primary},{outline},{back},0,0,0,0,100,100,0,0,3,3,2,2,30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]

    for seg in whisper_segments:
        s0 = float(seg.get("start", 0))
        e0 = float(seg.get("end", 0))
        if e0 <= clip_start or s0 >= clip_end:
            continue

        s1 = max(s0, clip_start)
        e1 = min(e0, clip_end)

        start = fmt_ass_time(s1 - clip_start)
        end = fmt_ass_time(e1 - clip_start)

        text = escape_ass_text((seg.get("text") or "").strip())
        if len(text) < 2:
            continue

        if len(text) > 44:
            mid = len(text) // 2
            cut = text.rfind(" ", 0, mid)
            if cut == -1:
                cut = mid
            text = text[:cut] + r"\N" + text[cut + 1 :]

        text = r"{\3c" + highlight + r"}" + text
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

    Path(ass_path).write_text("".join(lines), encoding="utf-8")


def burn_ass_subtitles(input_mp4: str, ass_path: str, output_mp4: str, fonts_dir: str):
    # Windows + FFmpeg: normalize + escape ":" do drive
    ass_path = ass_path.replace("\\", "/").replace(":", r"\:")
    fonts_dir = fonts_dir.replace("\\", "/").replace(":", r"\:")

    # dica: usar ass=filename=... ajuda a evitar parsing estranho
    vf = f"ass=filename='{ass_path}':fontsdir='{fonts_dir}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_mp4,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
        "-c:a", "copy",
        output_mp4
    ]
    run(cmd)



# =============================
# Clip selection
# =============================
def pick_best_clips(segments: List[Seg], max_clips: int) -> List[Tuple[float, float, str]]:
    """
    Escolhe segmentos por score e expande ate >= 60s.
    Retorna lista (start, end, texto_combinado).
    """
    if not segments:
        return []

    ranked = sorted(segments, key=lambda x: x.score, reverse=True)
    used: List[Tuple[float, float]] = []
    clips: List[Tuple[float, float, str]] = []

    def overlaps(a, b):
        return not (a[1] <= b[0] or b[1] <= a[0])

    for seg in ranked:
        if len(clips) >= max_clips:
            break

        idx = None
        for i, s in enumerate(segments):
            if s.start == seg.start and s.end == seg.end:
                idx = i
                break
        if idx is None:
            continue

        start = seg.start
        end = seg.end
        parts = [seg.text]

        left = idx - 1
        right = idx + 1

        while (end - start) < CLIP_MIN_SECONDS and (left >= 0 or right < len(segments)):
            left_score = segments[left].score if left >= 0 else -999
            right_score = segments[right].score if right < len(segments) else -999

            if right_score >= left_score and right < len(segments):
                end = segments[right].end
                parts.append(segments[right].text)
                right += 1
            elif left >= 0:
                start = segments[left].start
                parts.insert(0, segments[left].text)
                left -= 1
            else:
                break

            if CLIP_MAX_SECONDS and (end - start) > CLIP_MAX_SECONDS:
                end = start + float(CLIP_MAX_SECONDS)
                break

        if (end - start) < CLIP_MIN_SECONDS:
            continue

        candidate = (start, end)
        if any(overlaps(candidate, r) for r in used):
            continue

        used.append(candidate)
        clips.append((start, end, " ".join(parts).strip()))

    return sorted(clips, key=lambda x: x[0])


def main():
    tz = gettz(TIMEZONE)
    now = datetime.now(tz=tz)

    schedule_day = (now + timedelta(days=1)).date()  # começa amanhã
    schedule_slot = 0  # 0..4

    in_dir = Path(INPUT_DIR)
    out_dir = Path(OUTPUT_DIR)
    fonts_dir = str((Path(__file__).resolve().parent / "fonts").resolve())

    ensure_dir(in_dir)
    ensure_dir(out_dir)

    categories = sorted([p for p in in_dir.iterdir() if p.is_dir()])
    if not categories:
        print(f"Crie subpastas em {in_dir.resolve()} (ex.: pregacao/, desenvolvimento_pessoal/, revisar/)")
        return

    print("Carregando Whisper...")
    model = whisper.load_model(WHISPER_MODEL)

    total_clips = 0

    for cat_dir in categories:
        category = cat_dir.name
        videos = sorted([p for p in cat_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS])

        if not videos:
            print(f"\n[{category}] sem videos. Pulando.")
            continue

        print(f"\n=== Categoria: {category} ===")

        for video in videos:
            try:
                print(f"\nTranscrevendo: {video.name}")
                result = model.transcribe(str(video), fp16=False)
                wsegs = result.get("segments", [])

                segments: List[Seg] = []
                for s in wsegs:
                    text = (s.get("text") or "").strip()
                    if not text:
                        continue
                    segments.append(Seg(float(s["start"]), float(s["end"]), text, score_text(text)))

                segments.sort(key=lambda x: x.start)
                candidates = pick_best_clips(segments, max_clips=MAX_CLIPS_PER_VIDEO)

                if not candidates:
                    print("Nao achei trechos >= 1 minuto. Mantendo o video (nao apaga).")
                    continue

                cuts_created = 0

                for (s, e, combined_text) in candidates:
                    day = schedule_day
                    hhmm = POST_TIMES[schedule_slot]

                    schedule_slot += 1
                    if schedule_slot >= len(POST_TIMES):
                        schedule_slot = 0
                        schedule_day = schedule_day + timedelta(days=1)

                    day_folder = out_dir / category / day.strftime("%Y-%m-%d")
                    ensure_dir(day_folder)

                    hhmm_filename = hhmm.replace(":", "-")
                    clip_num = (len(list(day_folder.glob("*.mp4"))) + 1)
                    out_name = f"{hhmm_filename}_clip_{clip_num:02d}.mp4"
                    final_path = day_folder / out_name

                    temp_clip = day_folder / f"_temp_{out_name}"
                    print(f"Cortando 9:16 {out_name} ({s:.1f}s -> {e:.1f}s)")
                    ffmpeg_cut_tiktok(str(video), s, e, str(temp_clip))

                    thumb = day_folder / f"{out_name.replace('.mp4','')}_thumb.png"
                    mid_rel = max(0.3, (e - s) / 2.0)
                    try:
                        extract_thumbnail(str(temp_clip), mid_rel, str(thumb))
                        accent = pick_accent_color(video.name + out_name, str(thumb))
                    except Exception:
                        accent = pick_accent_color(video.name + out_name, None)

                    seed_text = combined_text + out_name + category
                    caption = make_caption_long(combined_text, category, seed_text=seed_text)

                    captions_file = day_folder / "captions.txt"
                    with open(captions_file, "a", encoding="utf-8") as f:
                        f.write(f"[{out_name}]\n{caption}\n\n---\n\n")

                    if BURN_CAPTIONS_IN_VIDEO:
                        ass_path = day_folder / f"{out_name.replace('.mp4','.ass')}"
                        write_ass_from_whisper_segments(
                            whisper_segments=wsegs,
                            clip_start=s,
                            clip_end=e,
                            ass_path=str(ass_path.resolve()),
                            font_name=CAPTION_FONT_NAME,
                            font_size=CAPTION_FONT_SIZE,
                            margin_v=CAPTION_MARGIN_V,
                            primary_hex="#FFFFFF",
                            outline_hex="#000000",
                            highlight_hex=accent,
                        )
                        burn_ass_subtitles(str(temp_clip), str(ass_path.resolve()), str(final_path), fonts_dir=fonts_dir)
                    else:
                        temp_clip.replace(final_path)

                    try:
                        temp_clip.unlink(missing_ok=True)
                    except Exception:
                        pass

                    if not KEEP_DEBUG_FILES:
                        try:
                            thumb.unlink(missing_ok=True)
                        except Exception:
                            pass
                        try:
                            (day_folder / f"{out_name.replace('.mp4','.ass')}").unlink(missing_ok=True)
                        except Exception:
                            pass

                    cuts_created += 1
                    total_clips += 1

                if cuts_created > 0:
                    try:
                        video.unlink()
                        print(f"Video original removido: {video.name}")
                    except Exception as ex:
                        print(f"Nao consegui apagar {video.name}: {ex}")

            except Exception as e:
                print(f"Erro processando {video.name}: {e}")
                continue

    print(f"\nTudo pronto. Total de cortes: {total_clips}")
    print(f"Saida em: {out_dir.resolve()}")


if __name__ == "__main__":
    main()

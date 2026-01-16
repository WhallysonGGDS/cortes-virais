# 🎬 Cortes Virais — Pipeline Profissional de Automação de Conteúdo

Projeto completo para **automatizar a produção de cortes virais** a partir de vídeos longos, usando **Python, Whisper e FFmpeg**.  
Ideal para **TikTok, Instagram Reels e YouTube Shorts**.

Este repositório entrega uma **linha de produção de conteúdo**, do download até o vídeo final legendado e organizado.

---

## 🧠 Visão Geral do Pipeline

O projeto funciona em **duas etapas automáticas**:

1. **Classificação Inteligente**
   - Monitora a pasta *Downloads*
   - Transcreve um preview curto do vídeo
   - Decide automaticamente a categoria do conteúdo
   - Move o vídeo para a pasta correta

2. **Geração de Cortes**
   - Analisa o vídeo completo
   - Identifica trechos com maior potencial viral
   - Cria cortes verticais (9:16)
   - Queima legendas no vídeo
   - Gera captions prontas com hashtags
   - Organiza tudo por data e horário

---

## 🚀 Funcionalidades

### 🔍 Classificação Automática (`auto_sort_downloads.py`)
- Monitoramento contínuo da pasta Downloads
- Uso do **Whisper (modelo tiny)** para classificação rápida
- Análise semântica baseada em palavras-chave
- Categorias:
  - `pregacao`
  - `desenvolvimento_pessoal`
  - `revisar`

### ✂️ Geração de Cortes (`cutter.py`)
- Transcrição completa com Whisper
- Score de viralização por heurística
- Cortes entre **60s e 180s**
- Conversão automática para **9:16**
- Modos:
  - `BLUR` (fundo desfocado)
  - `CROP` (corte direto)

### 🔤 Legendas Embutidas
- Geração automática de arquivos `.ass`
- Renderização via FFmpeg
- Fonte, tamanho e cores configuráveis
- Destaque visual em palavras-chave

### 📝 Captions Prontas
- Arquivo `captions.txt` por dia
- Texto longo + CTA
- Hashtags inteligentes por categoria
- Evita repetição excessiva

### 🗂️ Organização Profissional
- Separação por categoria
- Pastas por data (`YYYY-MM-DD`)
- Arquivos nomeados por horário de postagem
- Pronto para workflow de social media

---

## 📂 Estrutura do Projeto

```
cortes_virais/
├─ auto_sort_downloads.py
├─ cutter.py
├─ input_videos/
│  ├─ pregacao/
│  ├─ desenvolvimento_pessoal/
│  └─ revisar/
├─ output/
│  └─ <categoria>/
│     └─ <YYYY-MM-DD>/
│        ├─ 10-00_clip_01.mp4
│        ├─ 12-00_clip_02.mp4
│        └─ captions.txt
├─ fonts/
├─ requirements.txt
└─ README.md
```

---

## ⚙️ Requisitos

### 🐍 Python
- Python **3.10+**
- Recomendado uso de `venv`

### 🎥 FFmpeg
- Obrigatório
- Deve estar disponível no PATH

Teste:
```
ffmpeg -version
```

### 📦 Dependências

```
pip install -r requirements.txt
```

Caso Whisper apresente erro com Torch:
```
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

---

## ▶️ Como Executar

### 1️⃣ Criar ambiente virtual
```
python -m venv venv
venv\Scripts\Activate.ps1
```

### 2️⃣ Rodar classificador automático
```
python auto_sort_downloads.py
```

> Pode ficar rodando em segundo plano.

### 3️⃣ Baixar vídeos normalmente
- YouTube
- Podcasts
- Palestras
- Aulas

Eles serão movidos automaticamente para `input_videos/`.

### 4️⃣ Gerar cortes
```
python cutter.py
```

Os vídeos finais estarão em `output/`.

---

## 🔧 Configurações Importantes

No topo dos scripts:

### `auto_sort_downloads.py`
- `WHISPER_MODEL`
- `PREVIEW_SECONDS`
- `PREVIEW_OFFSET_SECONDS`

### `cutter.py`
- `POST_TIMES`
- `CLIP_MIN_SECONDS`
- `CLIP_MAX_SECONDS`
- `MAX_CLIPS_PER_VIDEO`
- `TIKTOK_MODE`
- `CAPTION_FONT_NAME`
- `CAPTION_FONT_SIZE`

---

## 🧯 Problemas Comuns

### ❌ FFmpeg não encontrado
➡️ Adicione ao PATH

### ❌ Classificação lenta
➡️ Reduza `PREVIEW_SECONDS` ou use modelo `tiny`

### ❌ Fonte não aparece
➡️ Verifique a pasta `fonts/`

---

## 🗺️ Roadmap

- Execução com um único comando
- Dashboard de métricas (CSV/JSON)
- Cache de transcrição
- Upload automático para redes sociais
- Interface gráfica

---

## 👤 Autor

**Whallyson Gabriel Garcia**  
Projeto focado em automação, escala e performance para criação de conteúdo.

---

## 📄 Licença

Uso livre para fins pessoais e comerciais.

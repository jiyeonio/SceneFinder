"""0단계 인코더 실측: 합성 복지 화면 글자 검색(한국어 질의→이미지 R@1) + 실제 영상 프레임 처리 속도.

합성 화면 30종(제목 크게 / 서류 목록 안 작은 글자) × 질의 2종(화면 글자 그대로 / 바꿔 말한 질의).
속도는 영상에서 2초마다 뽑은 640×360 프레임으로 잰다. 결과: results/encoder_probe.json

    python ai/experiments/vlm_model/encoder_probe.py --font NanumGothic-Regular.ttf \
        --video ~/scenefinder_eval/videos/HsV9CMmEvFo.mp4 \
        --models mclip,siglip2_base,siglip2_so400m,qwen3vl_emb2b --out <출력 접두어>

한국어 폰트는 서버에 없어 Google Fonts의 NanumGothic-Regular.ttf(OFL)를 따로 받아 썼다
(NotoSansKR 가변 폰트는 PIL에서 글자가 그려지지 않음).
"""
import argparse, json, random, subprocess, time
import numpy as np, torch
from PIL import Image, ImageDraw, ImageFont

# (화면 글자, 바꿔 말한 질의)
PAIRS = [
    ("기초연금 신청서", "노인 연금 신청 양식"), ("주민등록등본", "주소가 나온 주민센터 발급 서류"),
    ("가족관계증명서", "가족 관계를 증명하는 서류"), ("통장 사본", "은행 계좌 복사본"),
    ("소득·재산 신고서", "수입과 재산을 적는 서류"), ("장애인 등록 신청", "장애 등록하는 방법"),
    ("긴급복지 지원 신청", "갑자기 생활이 어려울 때 받는 지원"), ("아동수당 신청", "아이 키우는 집이 받는 수당"),
    ("부모급여 신청", "영아 부모에게 주는 돈"), ("국민연금 예상 수령액", "연금을 나중에 얼마 받는지"),
    ("기초생활수급자 선정", "생계급여 받는 사람 고르는 기준"), ("주거급여 신청", "집세 지원받기"),
    ("의료급여 안내", "병원비 지원 제도"), ("에너지바우처", "겨울 난방비 지원"),
    ("노인 일자리 사업", "어르신 일자리 구하기"), ("복지로 로그인", "복지 사이트에 들어가기"),
    ("공동인증서 선택", "인증서로 본인 확인하기"), ("온라인 신청하기", "신청 버튼 누르는 화면"),
    ("제출 서류 목록", "내야 할 서류 리스트"), ("행정복지센터 방문 신청", "동사무소에 가서 신청"),
    ("보건복지상담센터 129", "복지 상담 전화번호"), ("한부모가족 지원", "혼자 아이 키우는 가정 지원"),
    ("청년월세 지원", "젊은 사람 월세 도와주는 제도"), ("산모·신생아 건강관리", "출산 후 돌봐주는 서비스"),
    ("장기요양등급 신청", "요양 등급 받는 방법"), ("치매 조기검진", "기억력 검사 받기"),
    ("첫만남이용권", "아기 태어나면 주는 바우처"), ("실업급여 신청", "일자리를 잃었을 때 받는 돈"),
    ("근로장려금 신청", "일하는 저소득 가구 지원금"), ("문화누리카드 발급", "문화생활 지원 카드 만들기"),
]
FILLER = ["성명", "생년월일", "연락처", "주소", "신청인 정보", "확인", "취소", "다음 단계", "개인정보 동의", "이전"]


def render(key, mode, font, seed):
    rnd = random.Random(seed)
    im = Image.new("RGB", (1280, 720), (245, 247, 250)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1280, 70], fill=(30, 80, 160)); d.text((30, 14), "복지 서비스 안내", font=font(36), fill="white")
    items = rnd.sample(FILLER, 6)
    if mode == "title":
        d.text((80, 120), key, font=font(64), fill=(20, 20, 20))
        y = 250
    else:  # 목록 안 작은 글자
        items.insert(rnd.randrange(1, 6), key); y = 120
    for it in items:
        d.rectangle([80, y, 760, y + 56], outline=(180, 180, 190), width=2, fill="white")
        d.text((100, y + 12), it, font=font(26), fill=(40, 40, 40)); y += 72
    d.rounded_rectangle([900, 600, 1200, 670], 12, fill=(30, 80, 160)); d.text((960, 615), "확인", font=font(30), fill="white")
    return im


def video_frames(path, step=2.0, limit=None):
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]))
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps=1/{step},scale=640:360", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    w, h = 640, 360; n = len(out) // (w * h * 3)
    fr = [Image.fromarray(np.frombuffer(out, np.uint8, w * h * 3, i * w * h * 3).reshape(h, w, 3)) for i in range(n)]
    return fr[:limit] if limit else fr, dur


class Enc:
    def __init__(self, name):
        self.name = name; dev = "cuda"
        if name == "mclip":
            from sentence_transformers import SentenceTransformer
            from transformers import CLIPModel, CLIPProcessor
            self.t = SentenceTransformer("sentence-transformers/clip-ViT-B-32-multilingual-v1", device=dev)
            self.m = CLIPModel.from_pretrained("openai/clip-vit-base-patch32", torch_dtype=torch.float16).to(dev).eval()
            self.p = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        elif name.startswith("siglip2"):
            from transformers import AutoModel, AutoProcessor
            rid = {"siglip2_base": "google/siglip2-base-patch16-224", "siglip2_so400m": "google/siglip2-so400m-patch16-384"}[name]
            self.m = AutoModel.from_pretrained(rid, torch_dtype=torch.float16).to(dev).eval(); self.p = AutoProcessor.from_pretrained(rid)
        elif name == "qwen3vl_emb2b":
            from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
            rid = "Qwen/Qwen3-VL-Embedding-2B"
            self.m = Qwen3VLForConditionalGeneration.from_pretrained(rid, dtype=torch.bfloat16).model.to(dev).eval()
            self.p = AutoProcessor.from_pretrained(rid, padding_side="right")

    def _qwen(self, contents, instr, images=None):
        # Qwen3-VL-Embedding 방식: system 지시문 + user 입력, 생성 프롬프트까지 붙인 뒤 마지막 토큰 hidden state를 L2 정규화
        msgs = [[{"role": "system", "content": [{"type": "text", "text": instr}]}, {"role": "user", "content": c}] for c in contents]
        texts = self.p.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        x = self.p(text=texts, images=images, padding=True, return_tensors="pt").to("cuda")
        h = self.m(**x).last_hidden_state
        last = x["attention_mask"].sum(1) - 1
        return h[torch.arange(h.shape[0], device=h.device), last]

    @torch.no_grad()
    def text(self, qs):
        if self.name == "mclip":
            e = self.t.encode(qs, convert_to_tensor=True)
        elif self.name.startswith("siglip2"):
            x = self.p(text=qs, padding="max_length", max_length=64, truncation=True, return_tensors="pt").to("cuda")
            e = self.m.get_text_features(**x)
        else:
            e = self._qwen([[{"type": "text", "text": q}] for q in qs], "Retrieve images or video frames relevant to the user's query.")
        e = getattr(e, "pooler_output", e)
        return torch.nn.functional.normalize(e.float(), dim=-1)

    @torch.no_grad()
    def image(self, ims, bs=32):
        outs = []
        for i in range(0, len(ims), bs):
            b = ims[i:i + bs]
            if self.name == "qwen3vl_emb2b":
                e = torch.cat([self._qwen([[{"type": "image", "image": x}] for x in b[j:j + 8]], "Represent the user's input.", b[j:j + 8]) for j in range(0, len(b), 8)])
            else:
                x = self.p(images=b, return_tensors="pt").to("cuda")
                e = self.m.get_image_features(pixel_values=x["pixel_values"].half())
            e = getattr(e, "pooler_output", e)
            outs.append(torch.nn.functional.normalize(e.float(), dim=-1))
        return torch.cat(outs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font"); ap.add_argument("--video"); ap.add_argument("--models"); ap.add_argument("--out")
    a = ap.parse_args()
    font = lambda s: ImageFont.truetype(a.font, s)
    keys = [k for k, _ in PAIRS]
    imgs = {m: [render(k, m, font, i) for i, k in enumerate(keys)] for m in ("title", "list")}
    imgs["title"][0].save(a.out + ".sample_title.png"); imgs["list"][0].save(a.out + ".sample_list.png")
    frames, dur = video_frames(a.video)
    res = {}
    for name in a.models.split(","):
        torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
        enc = Enc(name); r = {}
        for qt, qs in (("exact", keys), ("paraphrase", [p for _, p in PAIRS])):
            t = enc.text(qs)
            for mode in ("title", "list"):
                s = t @ enc.image(imgs[mode]).T
                r[f"{qt}/{mode}"] = float((s.argmax(1).cpu() == torch.arange(len(keys))).float().mean())
        enc.image(frames[:16]); torch.cuda.synchronize(); t0 = time.time()
        enc.image(frames); torch.cuda.synchronize(); el = time.time() - t0
        t0 = time.time(); [enc.text(["기초연금 신청 방법을 설명하는 장면"]) for _ in range(20)]; torch.cuda.synchronize()
        r.update(frames=len(frames), video_sec=round(dur), encode_sec=round(el, 2), sec_per_video_min=round(el / dur * 60, 2),
                 query_ms=round((time.time() - t0) / 20 * 1000, 1), peak_gib=round(torch.cuda.max_memory_allocated() / 2**30, 2))
        res[name] = r; print(name, json.dumps(r, ensure_ascii=False), flush=True)
        del enc
    json.dump(res, open(a.out + ".json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

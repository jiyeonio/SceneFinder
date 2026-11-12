"""작은 LoRA 구현 (peft 없이). 원래 저장소의 가상환경을 공유하고 있어 패키지를 새로 설치하지 않고 직접 구현했다.

대상: 언어 모델 attention q·k·v·o (vlm_model_plan.md 「화면 검색 LoRA」). 시각 인코더는 건드리지 않는다.
"""
import math, re

import torch
import torch.nn as nn

TARGET = re.compile(r"language_model\.layers\.\d+\.self_attn\.(q|k|v|o)_proj$")


class LoRALinear(nn.Module):
    def __init__(self, base: nn.Linear, r, alpha, dropout):
        super().__init__()
        self.base = base
        self.r, self.scale = r, alpha / r
        self.A = nn.Parameter(torch.empty(r, base.in_features, dtype=torch.float32, device=base.weight.device))
        self.B = nn.Parameter(torch.zeros(base.out_features, r, dtype=torch.float32, device=base.weight.device))
        nn.init.kaiming_uniform_(self.A, a=math.sqrt(5))
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        y = self.base(x)
        d = (self.drop(x).to(self.A.dtype) @ self.A.t()) @ self.B.t()
        return y + (d * self.scale).to(y.dtype)


def apply_lora(model, r=16, alpha=32, dropout=0.05):
    for p in model.parameters():
        p.requires_grad_(False)
    names = [n for n, m in model.named_modules() if isinstance(m, nn.Linear) and TARGET.search(n)]
    assert names, "LoRA 대상 층을 찾지 못함"
    for n in names:
        parent, child = n.rsplit(".", 1)
        mod = model.get_submodule(parent)
        setattr(mod, child, LoRALinear(getattr(mod, child), r, alpha, dropout))
    return names


def lora_state(model):
    return {n: p.detach().cpu() for n, p in model.named_parameters() if n.endswith(".A") or n.endswith(".B")}


def load_lora(model, path, r=16, alpha=32):
    sd = torch.load(path, map_location="cpu")
    apply_lora(model, r, alpha, 0.0)
    missing = model.load_state_dict(sd, strict=False)
    assert not [k for k in missing.unexpected_keys], missing.unexpected_keys
    model.eval()
    return model

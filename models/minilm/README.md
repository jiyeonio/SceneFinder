---
tags:
- sentence-transformers
- sentence-similarity
- feature-extraction
- dense
- generated_from_trainer
- dataset_size:15502
- loss:MultipleNegativesRankingLoss
base_model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
widget:
- source_sentence: 튀긴 강낭콩은 색깔이 예쁘고 고소한 맛이 난다.
  sentences:
  - 냉동 식품인데도 냉동 식품 아닌 느낌이에요. 고기가 굉장히 부드러워. 날씨 풀리면 이제 뭐 캠핑 갈 때나 아니면 펜션으로 놀러갈 때나 가볍게
    술 안주로든 아니면 그다음 날 라면 대신 진짜 고급진 이색적이고 특별한 한끼 식사를 한번 드셔보시고 싶을 땐 요 우육면 진짜 추천드리니까 꼭
    한번 드셔보시길 바라요. 이거 진짜 대박 맛있어.
  - 튀기는 내내 그냥 군침 돌고 있습니다. 이렇게 강낭콩을 튀겨 놓으니까 색깔이 이쁘죠? 은은하게 입혀져 갖고 고소함이 그냥 풍미를 자아내고 있습니다.
    이대로 드시면은 고소한 맛이 나고요. 이 강낭콩을 약간 달게 먹고 싶다 하시는 분들은
  - 아따 맛있게 쪄졌네요. 이렇게 살짝만 찌면 됩니다. 아직도 살짝 덜 익었거든요. 이 정도가 마치 맞습니다. 그대로 들어내고요. 약간 이 정도만
    익어도 잘 썰어지거든요. 오징어를 데치지 않고 생으로 썰면은 엄청 힘듭니다. 오징어가 어느 정도 식은 다음에 썰도록 하겠습니다. 오징어가 식을
    동안 야채부터 썰어 보겠습니다. 양파는 반개입니다.
- source_sentence: 원당, 매실청 반 컵씩 넣고 땡기는 맛이 나는 오늘의 포인트인 뜨거운 물에 30분 불려놓은 감초 1개를 넣고 가스
    불 켜준다.
  sentences:
  - 얼마나 맛있게 보입니까? 맛살하고 당근, 새송이버섯, 김밥용 햄, 오이, 단무지,최고 앙상블 아닙니까? 주부님들 이전은 추석 때 부처 놓으면
    일등 가볼 겁니다. 꼭 한번 해보십시오. 지금까지 @이름1 셰프였습니다.
  - 고흥산 굴이라고 하는데요. 큼지막하니 신선해 보입니다. 소스 살짝 올려서 한입에 꿀꺽 했는데요. 크리미 하고 신선한 맛이 바다의 우유 라는
    말을 증명하는 것 같습니다. 혹시 방문 했는데 굴이 있으면 완전 추천하고 싶네요. 스테이크 굽는데 시간이 조금 오래 걸린다고 해서 미리 주문을
    받았습니다.
  - 원당 반 컵, 매실청 반 컵, 감초 1개를 뜨거운 물에 한 30분 불려왔거든요. 이 감초가 들어가면요 땡기는 맛이 나거든요. 오늘의 포인트입니다.
    감초 넣고 가스 불 켜줍니다.
- source_sentence: 불닭 스리라차 소스는 깔끔한 매운맛을 느낄 수 있고 저지방이라 걱정 없이 즐길 수 있는 삼양 불닭 스리라차 소스로,
    시큼한 맛을 싫어하는 사람들에게도 매콤하고 고유의 맛을 제공하며 화자가 이 소스와 먹으면 맛있는 요리를 보여 준다고 말한다.
  sentences:
  - 이렇게 이제 잘 풀어졌으면은요. 여기다가 인자 원당 수북하게 세 스푼 넣습니다. 이렇게 원당을 넣고 인자 한번 저어주세요. 원당이 없으신 분들은요
    설탕을 넣으셔도 괜찮습니다. 이렇게 인자 원당이 다 녹았으면은 밥솥에 삭히도록 하겠습니다.
  - 간지 나게 굴러가야 하는데 어렵네요. 오늘은 채널에 광고가 들어 왔어요. 이름하여 불닭 스리라차 소스 오늘은 이 소스로 먹으면 맛있는 요리
    몇 개 보여 드릴게요. 깔끔한 매운맛으로 즐길 수 있는 삼양 불닭 스리라차 저지방이라 살찔 걱정 없이 알룰로스 깔끔하게 매콤한 맛의 소스 스리라차
    소스의 고유의 시큼한 맛을 싫어하는 사람들도 삼양 불닭 스리라차라면
  - 을지로에 노포가 참 많지만 이렇게 오래된 노포도 드문것 같습니다. 강산옥은 가게 운영방침이 독특한데요. 오전11시30분부터 오후 2시까지만
    영업을 하구요. 1월은 아예 그냥 문을 닫습니다. 그리고 콩비지의 단일 메뉴만 판매하지만 콩비지는 5월까지만 판매를 하구요. 6월부터 9월까지는
    콩국수만 판매하는 점도 독특하죠.
- source_sentence: 생태도 푸짐하게 들어있고 그리고 고니와 알에서 정말 많이 놀랬고 다른 곳에서는 한번도 먹어 본적 없는 식감과 맛이
    였다고 한다.
  sentences:
  - 자 우리 친구들 안녕 안녕 @이름1입니다. 워니찌와 반갑습니다. 오늘은 제가 무엇을 준비를 했느냐 바로바로 앤티앤스의 아몬드 크림치즈 스틱과
    이 이건 무엇이냐 고구마 크림치즈 스틱을 가져왔어요. 이게 이제 무엇이냐 신메뉴인가? 아니
  - 아까도 얘기했듯이 마늘이 지방 분해를 해 줍니다. 그래서 인자 마늘하고 미역하고 물 쪼금 부어 갖고 이거 인자 볶아 줄 겁니다. 까스 불을
    켜 줍니다. 그리고 국간장 2스푼 사용합니다. 간이 쫌 배야 되거든요.
  - 우와 고니도 우와 생태도 푸짐하게 들어있고 고니와 알도 푸짐하게 들어있었습니다. 그리고 바로 이 고니와 알에서 정말 많이 놀랬는데요. 다른
    곳에서는 한 번도 먹어 본 적 없는 식감과 맛이었습니다. 알을 숟가락으로 자르면 알이 퍼져 나오면서 부드럽게 흩어지는데요. 입 안에서도 와르르
    퍼지는 듯한 느낌입니다.
- source_sentence: 베이컨 해쉬 버거는 40대 여성이 좋아하는 해쉬 브라운과 베이컨이 들어 있다.
  sentences:
  - 베이컨 해쉬 이거 포장지도 되게 약간 신경 많이 쓴 것 같애. 오 와 기름기 베이컨 해쉬 아 내가 진짜 좋아하는 거다. 해쉬 브라운에 베이컨까지
    있어. 까꿍
  - 운동 갔다 올 때 살짝 이거 밖에 해동을 해 놨어요. 그래서 어? 벌써 맛있는 냄새 나는데 어 요렇게 뭔가 약간 나또쓰한 그런 느낌이 딱 드는데
    요런 요렇게 딱 봐도 대두 같은 느낌 이게 보니까 흰 강낭콩이 무려 95.5프로
  - 이래서 인자 똘똘 말아줍니다. 이렇게 해서 인자 쭉 당기고요. 반만 당기고 인자 계란물 좀 남은 거 있어요. 계란물 남은 것을 부어주면 됩니다.
    이렇게 다 됐을 때 이제 가스 불 끄고요. 그대로 이제 김발대에다가 인자
pipeline_tag: sentence-similarity
library_name: sentence-transformers
---

# SentenceTransformer based on sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

This is a [sentence-transformers](https://www.SBERT.net) model finetuned from [sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2). It maps sentences & paragraphs to a 384-dimensional dense vector space and can be used for semantic textual similarity, semantic search, paraphrase mining, classification, clustering, and more.

## Model Details

### Model Description
- **Model Type:** Sentence Transformer
- **Base model:** [sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) <!-- at revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42 -->
- **Maximum Sequence Length:** 128 tokens
- **Output Dimensionality:** 384 dimensions
- **Similarity Function:** Cosine Similarity
- **Supported Modality:** Text
<!-- - **Training Dataset:** Unknown -->
<!-- - **Language:** Unknown -->
<!-- - **License:** Unknown -->

### Model Sources

- **Documentation:** [Sentence Transformers Documentation](https://sbert.net)
- **Repository:** [Sentence Transformers on GitHub](https://github.com/huggingface/sentence-transformers)
- **Hugging Face:** [Sentence Transformers on Hugging Face](https://huggingface.co/models?library=sentence-transformers)

### Full Model Architecture

```
SentenceTransformer(
  (0): Transformer({'transformer_task': 'feature-extraction', 'modality_config': {'text': {'method': 'forward', 'method_output_name': 'last_hidden_state'}}, 'module_output_name': 'token_embeddings', 'architecture': 'BertModel'})
  (1): Pooling({'embedding_dimension': 384, 'pooling_mode': 'mean', 'include_prompt': True})
)
```

## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```
Then you can load this model and run inference.
```python
from sentence_transformers import SentenceTransformer

# Download from the 🤗 Hub
model = SentenceTransformer("sentence_transformers_model_id")
# Run inference
sentences = [
    '베이컨 해쉬 버거는 40대 여성이 좋아하는 해쉬 브라운과 베이컨이 들어 있다.',
    '베이컨 해쉬 이거 포장지도 되게 약간 신경 많이 쓴 것 같애. 오 와 기름기 베이컨 해쉬 아 내가 진짜 좋아하는 거다. 해쉬 브라운에 베이컨까지 있어. 까꿍',
    '운동 갔다 올 때 살짝 이거 밖에 해동을 해 놨어요. 그래서 어? 벌써 맛있는 냄새 나는데 어 요렇게 뭔가 약간 나또쓰한 그런 느낌이 딱 드는데 요런 요렇게 딱 봐도 대두 같은 느낌 이게 보니까 흰 강낭콩이 무려 95.5프로',
]
embeddings = model.encode(sentences)
print(embeddings.shape)
# [3, 384]

# Get the similarity scores for the embeddings
similarities = model.similarity(embeddings, embeddings)
print(similarities)
# tensor([[1.0000, 0.8417, 0.0454],
#         [0.8417, 1.0000, 0.0264],
#         [0.0454, 0.0264, 1.0000]])
```
<!--
### Direct Usage (Transformers)

<details><summary>Click to see the direct usage in Transformers</summary>

</details>
-->

<!--
### Downstream Usage (Sentence Transformers)

You can finetune this model on your own dataset.

<details><summary>Click to expand</summary>

</details>
-->

<!--
### Out-of-Scope Use

*List how the model may foreseeably be misused and address what users ought not to do with the model.*
-->

<!--
## Bias, Risks and Limitations

*What are the known or foreseeable issues stemming from this model? You could also flag here known failure cases or weaknesses of the model.*
-->

<!--
### Recommendations

*What are recommendations with respect to the foreseeable issues? For example, filtering explicit content.*
-->

## Training Details

### Training Dataset

#### Unnamed Dataset

* Size: 15,502 training samples
* Columns: <code>anchor</code> and <code>positive</code>
* Approximate statistics based on the first 100 samples:
  |          | anchor                                                                             | positive                                                                            |
  |:---------|:-----------------------------------------------------------------------------------|:------------------------------------------------------------------------------------|
  | type     | string                                                                             | string                                                                              |
  | modality | text                                                                               | text                                                                                |
  | details  | <ul><li>min: 12 tokens</li><li>mean: 29.16 tokens</li><li>max: 60 tokens</li></ul> | <ul><li>min: 43 tokens</li><li>mean: 92.22 tokens</li><li>max: 128 tokens</li></ul> |
* Samples:
  | anchor                                                                                                                 | positive                                                                                                                                                                                                                    |
  |:-----------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | <code>떡볶이에 버섯류가 없는 것이 아쉽고 분모자는 엽떡보다 마라 떡볶이에 들어간 것이 더 맛있었고 먹다 보니까 매웠습니다.</code>                                         | <code>아 그리고 버섯류 없는 것도 너무 아쉬워. 음 분모자는 엽떡에 들어가는 것보다 마라 떡볶이에 들어간 게 더 맛있다. 음 기본 오리지널보다 마라맛이 싹 배어있네. 아 이거 마라탕이라 생각했어. 떡을 너무 안 먹었다. 떡볶이지. 음 어 근데 먹다 보니까 맵다. 음 매워요.</code>                                                         |
  | <code>이 떡볶이는 마라 떡볶이인데 엽기 떡볶이에서 신제품이 나왔다고 해서 사 와봤습니다.</code>                                                            | <code>이거나 한 입 먹고 끝내야 했다. 야 이거 기름 그냥 그거다 그거 행주에 그거다. 야 이거 그냥 보이세요? 쭉 안 보이네. 쭉 헤엑 아니 안 먹을래. 자 유튜브 친구들 안녕하세요? @이름1입니다. 자 오늘 같은 경우에는요. 엽기 떡볶이에 신제품이 나왔어요. 엽떡을 제가 그렇게 좋아하진 않는데 이거는 먹어봐야겠다 싶어 가지고 사 왔거든요. 이게 지금 마라 떡볶이입니다.</code> |
  | <code>이 파스타는 처음 먹었을 때부터 우유를 넣고 만들어서 그런지 더 찐득찐득하고 맛이 있었고 파스타를 좋아하는 분들은 이게 인스턴트지만 맛있다고 느끼실 거라고 제가 자부할 수 있고 추천합니다.</code> | <code>네 다 먹었습니다. 아 진짜 맛있어요. 그때 처음했을 때도 우유를 넣어 가지고 먹었는데 우유를 넣어서 더 찐득찐득하고 맛있는 거 같아요. 면 음식의 맛은 제가 잘 안다고 자부할 수 있습니다. 네 파스타 좋아하는 분들은 이거 진짜 인스턴트지만 그래도 맛있다고 느끼실 거예요. 이거 추천할게요. 네 오늘은 또 첫 먹방 영상을 찍어봤는데요.</code>                    |
* Loss: [<code>MultipleNegativesRankingLoss</code>](https://sbert.net/docs/package_reference/sentence_transformer/losses.html#multiplenegativesrankingloss) with these parameters:
  ```json
  {
      "scale": 20.0,
      "similarity_fct": "cos_sim",
      "gather_across_devices": false,
      "directions": [
          "query_to_doc"
      ],
      "partition_mode": "joint",
      "hardness_mode": null,
      "hardness_strength": 0.0
  }
  ```

### Training Hyperparameters
#### Non-Default Hyperparameters

- `gradient_accumulation_steps`: 2
- `learning_rate`: 2e-05
- `num_train_epochs`: 1
- `warmup_ratio`: 0.1
- `data_seed`: 42
- `fp16`: True
- `batch_sampler`: no_duplicates

#### All Hyperparameters
<details><summary>Click to expand</summary>

- `overwrite_output_dir`: False
- `do_predict`: False
- `prediction_loss_only`: True
- `per_device_train_batch_size`: 8
- `per_device_eval_batch_size`: 8
- `per_gpu_train_batch_size`: None
- `per_gpu_eval_batch_size`: None
- `gradient_accumulation_steps`: 2
- `eval_accumulation_steps`: None
- `torch_empty_cache_steps`: None
- `learning_rate`: 2e-05
- `weight_decay`: 0.0
- `adam_beta1`: 0.9
- `adam_beta2`: 0.999
- `adam_epsilon`: 1e-08
- `max_grad_norm`: 1.0
- `num_train_epochs`: 1
- `max_steps`: -1
- `lr_scheduler_type`: linear
- `lr_scheduler_kwargs`: None
- `warmup_ratio`: 0.1
- `warmup_steps`: 0
- `log_level`: passive
- `log_level_replica`: warning
- `log_on_each_node`: True
- `logging_nan_inf_filter`: True
- `save_safetensors`: True
- `save_on_each_node`: False
- `save_only_model`: False
- `restore_callback_states_from_checkpoint`: False
- `no_cuda`: False
- `use_cpu`: False
- `use_mps_device`: False
- `seed`: 42
- `data_seed`: 42
- `jit_mode_eval`: False
- `bf16`: False
- `fp16`: True
- `fp16_opt_level`: O1
- `half_precision_backend`: auto
- `bf16_full_eval`: False
- `fp16_full_eval`: False
- `tf32`: None
- `local_rank`: 0
- `ddp_backend`: None
- `tpu_num_cores`: None
- `tpu_metrics_debug`: False
- `debug`: []
- `dataloader_drop_last`: False
- `dataloader_num_workers`: 0
- `dataloader_prefetch_factor`: None
- `past_index`: -1
- `disable_tqdm`: False
- `remove_unused_columns`: True
- `label_names`: None
- `load_best_model_at_end`: False
- `ignore_data_skip`: False
- `fsdp`: []
- `fsdp_min_num_params`: 0
- `fsdp_config`: {'min_num_params': 0, 'xla': False, 'xla_fsdp_v2': False, 'xla_fsdp_grad_ckpt': False}
- `fsdp_transformer_layer_cls_to_wrap`: None
- `accelerator_config`: {'split_batches': False, 'dispatch_batches': None, 'even_batches': True, 'use_seedable_sampler': True, 'non_blocking': False, 'gradient_accumulation_kwargs': None}
- `parallelism_config`: None
- `deepspeed`: None
- `label_smoothing_factor`: 0.0
- `optim`: adamw_torch_fused
- `optim_args`: None
- `adafactor`: False
- `group_by_length`: False
- `length_column_name`: length
- `project`: huggingface
- `trackio_space_id`: trackio
- `ddp_find_unused_parameters`: None
- `ddp_bucket_cap_mb`: None
- `ddp_broadcast_buffers`: False
- `dataloader_pin_memory`: True
- `dataloader_persistent_workers`: False
- `skip_memory_metrics`: True
- `use_legacy_prediction_loop`: False
- `push_to_hub`: False
- `resume_from_checkpoint`: None
- `hub_model_id`: None
- `hub_strategy`: every_save
- `hub_private_repo`: None
- `hub_always_push`: False
- `hub_revision`: None
- `gradient_checkpointing`: False
- `gradient_checkpointing_kwargs`: None
- `include_inputs_for_metrics`: False
- `include_for_metrics`: []
- `eval_do_concat_batches`: True
- `fp16_backend`: auto
- `push_to_hub_model_id`: None
- `push_to_hub_organization`: None
- `mp_parameters`:
- `auto_find_batch_size`: False
- `full_determinism`: False
- `torchdynamo`: None
- `ray_scope`: last
- `ddp_timeout`: 1800
- `torch_compile`: False
- `torch_compile_backend`: None
- `torch_compile_mode`: None
- `include_tokens_per_second`: False
- `include_num_input_tokens_seen`: no
- `neftune_noise_alpha`: None
- `optim_target_modules`: None
- `batch_eval_metrics`: False
- `eval_on_start`: False
- `use_liger_kernel`: False
- `liger_kernel_config`: None
- `eval_use_gather_object`: False
- `average_tokens_across_devices`: True
- `prompts`: None
- `batch_sampler`: no_duplicates
- `multi_dataset_batch_sampler`: proportional
- `router_mapping`: {}
- `learning_rate_mapping`: {}

</details>

### Training Logs
| Epoch  | Step | Training Loss |
|:------:|:----:|:-------------:|
| 0.1032 | 100  | 0.1812        |
| 0.2064 | 200  | 0.1092        |
| 0.3096 | 300  | 0.085         |
| 0.4128 | 400  | 0.0679        |
| 0.5160 | 500  | 0.0471        |
| 0.6192 | 600  | 0.0426        |
| 0.7224 | 700  | 0.0381        |
| 0.8256 | 800  | 0.0617        |
| 0.9288 | 900  | 0.0372        |


### Training Time
- **Training**: 6.8 minutes

### Framework Versions
- Python: 3.13.15
- Sentence Transformers: 5.7.0
- Transformers: 4.57.6
- PyTorch: 2.11.0+cu130
- Accelerate: 1.15.0
- Datasets: 4.8.5
- Tokenizers: 0.22.2

## Additional Resources

- [Training and Finetuning Embedding Models with Sentence Transformers](https://huggingface.co/blog/train-sentence-transformers): the end-to-end guide for training or finetuning Sentence Transformer models.
- [Introduction to Matryoshka Embedding Models](https://huggingface.co/blog/matryoshka): variable-size embeddings that can be truncated with minimal quality loss.
- [Binary and Scalar Embedding Quantization for Significantly Faster & Cheaper Retrieval](https://huggingface.co/blog/embedding-quantization): post-training compression of embedding vectors.
- [Multimodal Embedding & Reranker Models with Sentence Transformers](https://huggingface.co/blog/multimodal-sentence-transformers): use text, image, audio, and video models through the same API.
- [Training and Finetuning Multimodal Embedding & Reranker Models with Sentence Transformers](https://huggingface.co/blog/train-multimodal-sentence-transformers): train multimodal embedding models, with a Visual Document Retrieval walkthrough.

## Citation

### BibTeX

#### Sentence Transformers
```bibtex
@inproceedings{reimers-2019-sentence-bert,
    title = "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
    author = "Reimers, Nils and Gurevych, Iryna",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing",
    month = "11",
    year = "2019",
    publisher = "Association for Computational Linguistics",
    url = "https://arxiv.org/abs/1908.10084",
}
```

#### MultipleNegativesRankingLoss
```bibtex
@misc{oord2019representationlearningcontrastivepredictive,
      title={Representation Learning with Contrastive Predictive Coding},
      author={Aaron van den Oord and Yazhe Li and Oriol Vinyals},
      year={2019},
      eprint={1807.03748},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/1807.03748},
}
```

<!--
## Glossary

*Clearly define terms in order to be accessible across audiences.*
-->

<!--
## Model Card Authors

*Lists the people who create the model card, providing recognition and accountability for the detailed work that goes into its construction.*
-->

<!--
## Model Card Contact

*Provides a way for people who have updates to the Model Card, suggestions, or questions, to contact the Model Card authors.*
-->
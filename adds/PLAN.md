# Plan hoàn thành Lab Day 19 — Vector Store + Feature Store (Lite path)

> Mục tiêu: hoàn tất 4 notebooks + benchmark + submission, đạt **100/100** theo `rubric.md`, dùng path **Lite** (`setup-lite.sh`, không Docker).

---

## 0. Bối cảnh & yêu cầu môi trường

- **OS**: Windows (workspace hiện tại) → cần Git Bash / WSL để chạy `bash setup-lite.sh` (script dùng `set -euo pipefail` và `source .venv/bin/activate` kiểu Unix).
- **Python**: ≥ 3.10
- **Stack lite**: `fastembed` + `qdrant-client[memory]` + `rank-bm25` + `feast (sqlite)` + `FastAPI` + `jupytext` + `jupyterlab`.
- **Không cần**: Docker, GPU, OpenAI key.
- **RAM**: ~700 MB.

### Lưu ý Windows
Vì `setup-lite.sh` activate venv bằng `.venv/bin/activate` (Linux), trên Windows native nên:
- Dùng **Git Bash** (đường dẫn `.venv/Scripts/activate` trên Windows — script có thể fail ở step activate). Cách an toàn: chạy trong **WSL Ubuntu** hoặc tự thực hiện thủ công các bước tương đương trong PowerShell:
  1. `python -m venv .venv`
  2. `.venv\Scripts\Activate.ps1`
  3. `pip install -U pip && pip install -r requirements.txt`
  4. `jupytext --to notebook --update notebooks/*.py`
  5. `copy .env.example .env`
  6. `python scripts/seed_corpus.py`
  7. `python scripts/verify_lite.py`

---

## 1. Bản đồ deliverable → rubric

| Bullet slide | Notebook | Rubric pts | Pass khi |
|---|---|---:|---|
| 1. Index 1000 vectors + top-5 VN query | `01_embeddings_index` | 20 | `count == 1000`; paraphrase query đúng cluster `cloud` |
| 2. Hybrid > keyword & semantic | `02_hybrid_search_rrf` | 25 | RRF 1-based; avg P@10 hybrid cao nhất; slice `mixed` hybrid thắng |
| 3. FastAPI `/search` + P99 < 50ms | `03_search_api_benchmark` | 25 | Schema có `latency_ms`; bảng P50/P95/P99; hybrid P99 < 50ms |
| 4. Feast 3 views materialize + online | `04_feast_feature_store` | 25 | `feast apply` + `materialize-incremental` + `get_online_features` + PIT join 3 rows |
| Reproducible | toàn lab | 5 | Clean run `setup-lite.sh && make benchmark` thành công |

---

## 2. Roadmap thực thi (theo thứ tự)

### Phase A — Setup (≈ 15 phút)

- [x] **A1.** Đọc `VIBE-CODING.md` (5–10 phút) — bắt buộc trước NB1.
- [x] **A2.** Chạy `bash setup-lite.sh` (hoặc các bước thủ công Windows ở §0).
- [x] **A3.** Verify: `python scripts/verify_lite.py` báo `All checks passed`.
- [x] **A4.** Kiểm tra artifacts: `data/corpus_vn.jsonl` (1000 dòng), `data/golden_set.jsonl` (50 queries), `.env` đã copy.
- [x] **A5.** Mở Jupyter: `make lab` → http://localhost:8888.

### Phase B — NB1 `01_embeddings_index` (≈ 30 phút)

- [x] **B1.** Load corpus 1000 docs từ `data/corpus_vn.jsonl`.
- [x] **B2.** Embed bằng `fastembed` (model nhẹ, e.g. `BAAI/bge-small-en-v1.5` hoặc multilingual tương tự được seed sẵn).
- [x] **B3.** Index vào Qdrant in-memory (`QdrantClient(":memory:")` hoặc `path=":memory:"`).
- [x] **B4.** Assert `client.count("lab19").count == 1000`.
- [x] **B5.** Chạy 2 query: keyword query + paraphrase query (không chứa từ "cloud" nhưng kỳ vọng top-5 thuộc cluster `cloud`).
- [x] **B6.** Capture screenshot top-5 results + count → `submission/screenshots/nb1_*.png`.

### Phase C — NB2 `02_hybrid_search_rrf` (≈ 60 phút)

- [x] **C1.** Build BM25 index (`rank-bm25`) trên cùng corpus.
- [x] **C2.** Implement 3 hàm: `search_keyword`, `search_semantic`, `search_hybrid`.
- [x] **C3.** RRF công thức: `score(d) = Σ 1 / (k + rank_i(d))`, `k=60`, **rank 1-based**.
- [x] **C4.** Đánh giá Precision@10 trên 50 golden queries.
- [x] **C5.** Build 2 bảng:
  - Bảng tổng: avg P@10 cho `keyword | semantic | hybrid` → hybrid cao nhất.
  - Bảng slice theo `query_type ∈ {exact, paraphrase, mixed}` → BM25 thắng `exact`, vector thắng `paraphrase`, hybrid thắng `mixed`.
- [x] **C6.** Screenshot 2 bảng → `nb2_*.png`.

### Phase D — NB3 `03_search_api_benchmark` (≈ 45 phút)

- [x] **D1.** Hoàn thiện `app/main.py` với endpoint `GET /search?q=...&mode=keyword|semantic|hybrid&top_k=10` trả về `SearchResponse{results, latency_ms, mode}`.
- [x] **D2.** Hoàn thiện `app/search.py` (`Searcher` class re-use indices từ NB1/2; build 1 lần lúc app startup).
- [x] **D3.** Khởi động API: `make api` (port 8000). Test bằng `curl` hoặc `requests`.
- [x] **D4.** Trong notebook: warmup 10 queries → đo 100+ requests/mode → tính P50/P95/P99 từ field `latency_ms` (server-side).
- [x] **D5.** Verify hybrid P99 < 50ms. Nếu không đạt: tăng warmup, cache embed model, dùng batch.
- [x] **D6.** Screenshot bảng latency + 1 sample response JSON → `nb3_*.png`.

### Phase E — NB4 `04_feast_feature_store` (≈ 60 phút)

- [x] **E1.** Review/định nghĩa 3 feature views trong `app/feast_repo/feature_views.py`:
  - `user_profile_fv` (stable: tier, signup_date, ...)
  - `user_activity_fv` (rolling 7d / 30d events)
  - `doc_stats_fv` (per-doc views/clicks)
- [x] **E2.** `feature_store.yaml` cấu hình SQLite online store (lite mode).
- [x] **E3.** Chạy `feast apply` từ thư mục `app/feast_repo/` — verify `feast feature-views list` show 3 views.
- [x] **E4.** `feast materialize-incremental $(date -u +%Y-%m-%dT%H:%M:%S)` — capture log row counts.
- [x] **E5.** `store.get_online_features(features=[...], entity_rows=[{"user_id":"u_001"}])` → dict hợp lệ.
- [x] **E6.** Đo 100-call online lookup P99 (kỳ vọng < 10ms với SQLite local).
- [x] **E7.** PIT join: `store.get_historical_features(entity_df, features=[...]).to_df()` → 3 rows × N cols.
- [x] **E8.** Screenshot apply log + materialize log + online dict + PIT df → `nb4_*.png`.

### Phase F — Benchmark & Reproducibility (≈ 15 phút)

- [ ] **F1.** Chạy `make benchmark` → in bảng Precision@10 + P99 latency tổng hợp.
```bash
(.venv) west2light@DESKTOP-R0MD39H:~/lab19$ make benchmark
Day 19 benchmark — keyword vs semantic vs hybrid
==============================================================
  Loaded 50 golden queries
  Building Searcher (this may take ~30s on first run — embedding the corpus)...
  Indexed 1000 docs in 23.0s

Quality — Precision@10 (% of top-10 in matching topic)
  Keyword (BM25)   :  77.8%
  Semantic (vector):  73.2%
  Hybrid  (RRF=60) :  78.6%   <- should win

Quality by query type:
  type           n       kw     sem     hyb
  exact         15   96.7%  88.7%  96.7%
  paraphrase    15   33.3%  24.0%  32.0%
  mixed         20   97.0%  98.5% 100.0%

Latency — P50 / P95 / P99 over 5000 calls/mode
  keyword  : P50=   0.6ms  P95=   0.8ms  P99=   0.9ms
  semantic : P50=   4.1ms  P95=   5.3ms  P99=   6.4ms
  hybrid   : P50=   5.7ms  P95=   8.1ms  P99=   9.4ms

PASS — hybrid beats keyword by +0.8pp, semantic by +5.4pp
```
- [x] **F2.** (Optional) `make test` → pytest pass.
- [x] **F3.** Test reproducibility: `make clean-lite && bash setup-lite.sh && make benchmark` thành công clean.

### Phase G — Submission (≈ 20 phút)

- [x] **G1.** Đảm bảo 4 `.ipynb` còn output cells (không clear-output trước khi commit).
- [x] **G2.** Add screenshots vào `submission/screenshots/` (tối thiểu 1 ảnh / NB).
- [x] **G3.** Điền `submission/REFLECTION.md` (≤ 200 chữ): mode nào thắng query gì, khi nào *không* dùng hybrid.
- [ ] **G4.** Commit & push public repo:
  ```bash
  git add -A
  git commit -m "Lab 19 submission — Duong Quang Dong"
  git push -u origin main
  ```
- [x] **G5.** Verify repo **public** trên GitHub.
- [x] **G6.** Paste URL vào VinUni LMS Day-19 box.

### Phase H — Bonus (optional, +20pts)

- [x] **H1.** Tạo `bonus/ARCHITECTURE.md` ≥ 600 từ + diagram (mermaid OK).
- [x] **H2.** 3 architecture decisions có tradeoff X-vs-Y rõ ràng; ≥ 1 decision có Vietnamese context.
- [x] **H3.** `bonus/agent.py` cài `HybridMemoryAgent` với `.remember()` + `.recall()`.
- [x] **H4.** `bonus/demo.py` chạy 5 queries, exit 0.

---

## 3. Risk register & mitigations

| Risk | Triệu chứng | Fix |
|---|---|---|
| Activate venv fail trên Windows | `setup-lite.sh` lỗi ở `source .venv/bin/activate` | Dùng WSL hoặc làm thủ công bằng PowerShell (§0) |
| `count != 1000` | Chưa seed | `make seed` hoặc `python scripts/seed_corpus.py` |
| Hybrid không thắng | RRF rank 0-based hoặc `k` sai | Dùng `1/(60 + rank)`, rank bắt đầu từ 1 |
| P99 > 50ms | Cold start, model load mỗi request | Khởi tạo `Searcher` 1 lần ở app startup; warmup ≥ 10 query |
| `feast apply` lỗi registry | Cache cũ | `rm app/feast_repo/registry.db` rồi apply lại |
| Port 8000 / 8888 bận | API/Lab không start | Đổi `--port` hoặc kill process đang giữ |

---

## 4. Definition of Done

- [x] 4 notebooks `.ipynb` chạy end-to-end **với output cells**.
- [x] `make benchmark` in bảng đầy đủ; hybrid avg P@10 cao nhất; hybrid P99 < 50ms.
- [x] `feast apply` + `materialize-incremental` + `get_online_features` + PIT join đều xanh.
- [x] `submission/screenshots/` có ≥ 4 ảnh; `REFLECTION.md` ≤ 200 từ.
- [x] Repo public trên GitHub; URL submitted vào LMS.
- [x] Reproducible từ `clean-lite` → `setup-lite.sh` → `benchmark` không lỗi.

---

## 5. Time budget tổng

| Phase | Ước tính |
|---|---:|
| A. Setup | 15' |
| B. NB1 | 30' |
| C. NB2 | 60' |
| D. NB3 | 45' |
| E. NB4 | 60' |
| F. Benchmark | 15' |
| G. Submission | 20' |
| **Core total** | **~4h** |
| H. Bonus | +4–6h |

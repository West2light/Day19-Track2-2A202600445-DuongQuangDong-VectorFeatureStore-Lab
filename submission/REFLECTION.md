# Reflection — Lab 19

**Tên:** Dương Quang Đông
**Cohort:** A20-K1
**Path đã chạy:** lite

---

## Câu hỏi (≤ 200 chữ)

> Trên golden set 50 queries, mode nào thắng ở loại query nào (`exact` /
> `paraphrase` / `mixed`), và tại sao? Khi nào bạn **không** dùng hybrid
> (i.e. khi nào pure BM25 hoặc pure vector là lựa chọn đúng)?

Trên 50 golden queries, kết quả Precision@10 cho thấy phân hoá rõ theo loại
query:

- **`exact` (15 q)**: BM25 và Hybrid cùng đạt **96.7%**, vector chỉ 88.7%.
  Khi user gõ đúng từ khoá có trong corpus, lexical match là tín hiệu mạnh
  nhất; vector dễ bị "loãng" do paraphrase hàng xóm trong embedding space.
- **`paraphrase` (15 q)**: BM25 **33.3%** > Hybrid 32.0% > Semantic 24.0%.
  Corpus tiếng Việt + model embedding nhỏ (`bge-small`) chưa đủ mạnh cho
  ngữ nghĩa tiếng Việt, nên vector kéo Hybrid xuống. Đây là điểm yếu của
  setup lite, không phải của RRF.
- **`mixed` (20 q)**: Hybrid **100%** > Semantic 98.5% > BM25 97.0%.
  RRF tổng hợp được cả tín hiệu từ khoá và ngữ nghĩa → đúng "đất diễn".

**Khi nào KHÔNG dùng hybrid?**

1. Truy vấn ID/code/SKU/tên riêng → **pure BM25**: hybrid chỉ thêm noise
   và latency, vector không hiểu token hiếm.
2. Semantic search trên corpus đa ngôn ngữ với model embedding mạnh và
   query ngắn dạng câu hỏi tự nhiên → **pure vector**: BM25 không match
   được paraphrase, RRF không cải thiện.
3. Latency-critical (P99 < 5ms) hoặc corpus < 1k docs → BM25 đơn thuần đã
   đủ tốt, không đáng phải chạy 2 retriever + merge.

---

## Điều ngạc nhiên nhất khi làm lab này

Vector model `bge-small` (English-centric) thua BM25 ở nhánh `paraphrase`
tiếng Việt — nhắc tôi rằng "semantic > lexical" không phải định luật, mà
phụ thuộc rất mạnh vào **ngôn ngữ × kích thước model**. RRF không tự cứu
được vector yếu, nó chỉ khuếch đại tín hiệu sẵn có.

---

## Bonus challenge

- [x] Đã làm bonus (xem `bonus/`)
- [ ] Pair work với: _<tên đồng đội nếu có>_

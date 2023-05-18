#ifndef CTRANSFORMERS_MODELS_LLM_H_
#define CTRANSFORMERS_MODELS_LLM_H_

#include "common.h"

// https://github.com/marella/train/blob/3c4ba1f59bf20e31f7ee5ea9a8f38e49440a93f7/train/state.py#L135-L175
class RingBuffer {
 public:
  void Init(const int capacity) {
    capacity_ = capacity;
    Clear();
  }

  void Add(const gpt_vocab::id token) {
    if (Size() < capacity_) {
      tokens_.push_back(token);
    } else {
      tokens_[pos_] = token;
    }
    pos_ = (pos_ + 1) % capacity_;
  }

  // Returns last n tokens.
  std::unordered_set<gpt_vocab::id> GetRecent(int n) const {
    const int size = Size();
    n = std::min(size, n);
    std::unordered_set<gpt_vocab::id> result;
    if (n == 0) {
      return result;
    }
    const int start = (pos_ - n + size) % size;
    if (start < pos_) {
      result.insert(tokens_.begin() + start, tokens_.begin() + pos_);
    } else {
      result.insert(tokens_.begin() + start, tokens_.end());
      result.insert(tokens_.begin(), tokens_.begin() + pos_);
    }
    return result;
  }

  void Clear() {
    tokens_.clear();
    pos_ = 0;
  }

  int Size() const { return tokens_.size(); }

 private:
  int capacity_;
  std::vector<gpt_vocab::id> tokens_;
  int pos_ = 0;
};

class LLM {
 public:
  virtual ~LLM(){};

  bool Init(const std::string &filename) {
    if (initialized_) {
      return false;
    }
    if (!Load(filename)) {
      return false;
    }
    previous_tokens_.Init(ContextLength());
    return initialized_ = true;
  }

  std::vector<gpt_vocab::id> Tokenize(const std::string &text) const {
    return gpt_tokenize(vocab_, text);
  }

  const std::string &Detokenize(const gpt_vocab::id id) const {
    const auto it = vocab_.id_to_token.find(id);
    if (it == vocab_.id_to_token.end()) {
      return kEmptyString;
    }
    return it->second;
  }

  bool BatchEval(const std::vector<gpt_vocab::id> &tokens, const int batch_size,
                 const int threads) {
    const int size = tokens.size();
    for (int start = 0; start < size; start += batch_size) {
      const int end = std::min(start + batch_size, (int)tokens.size());
      const std::vector<gpt_vocab::id> batch(tokens.begin() + start,
                                             tokens.begin() + end);
      if (!EvalInternal(batch, threads)) {
        return false;
      }
    }
    return true;
  }

  gpt_vocab::id Sample(const int top_k, const float top_p,
                       const float temperature, const float repetition_penalty,
                       int last_n_tokens, int seed) const {
    if (logits_.empty()) {
      return EosToken();
    }
    if (last_n_tokens < 0) {
      last_n_tokens = ContextLength();
    }
    if (seed < 0) {
      seed = time(nullptr);
    }
    std::mt19937 rng(seed);

    std::unordered_set<gpt_vocab::id> recent_tokens;
    if (repetition_penalty != 1.0f) {
      recent_tokens = previous_tokens_.GetRecent(last_n_tokens);
    }

    return gpt_sample_top_k_top_p(
        vocab_, logits_.data() + (logits_.size() - VocabSize()), top_k, top_p,
        temperature, repetition_penalty, recent_tokens, rng);
  }

  bool IsEosToken(const gpt_vocab::id token) const {
    if (token == EosToken()) {
      return true;
    }
    // Handle special tokens in Dolly V2.
    if (!vocab_.special_tokens.empty()) {
      return Detokenize(token) == "### End";
    }
    return false;
  }

  void Reset() {
    logits_.clear();
    previous_tokens_.Clear();
  }

 protected:
  int n_ctx_ = -1;
  gpt_vocab vocab_;
  size_t mem_per_token_ = 0;
  std::vector<float> logits_;
  RingBuffer previous_tokens_;

  virtual bool Load(const std::string &filename) = 0;
  virtual bool Eval(const std::vector<gpt_vocab::id> &tokens, const int threads,
                    const int n_past) = 0;

 private:
  bool initialized_ = false;
  const std::string kEmptyString = "";

  bool EvalInternal(const std::vector<gpt_vocab::id> &tokens, int threads) {
    if (threads < 0) {
      threads = std::min((int)std::thread::hardware_concurrency(), 4);
    }
    const int n_past =
        std::min(ContextLength() - (int)tokens.size(), previous_tokens_.Size());
    if (!Eval(tokens, threads, n_past)) {
      return false;
    }
    for (const gpt_vocab::id token : tokens) {
      previous_tokens_.Add(token);
    }
    return true;
  }

  gpt_vocab::id EosToken() const {
    const auto it = vocab_.token_to_id.find("<|endoftext|>");
    if (it != vocab_.token_to_id.end()) {
      return it->second;
    }
    return 0;
  }

  int ContextLength() const { return n_ctx_; }

  int VocabSize() const { return vocab_.id_to_token.size(); }
};

#define REGISTER_LLM(_name)                                                \
  class _name##_llm : public LLM {                                         \
   public:                                                                 \
    virtual ~_name##_llm() {                                               \
      if (model_.ctx != nullptr) {                                         \
        ggml_free(model_.ctx);                                             \
      }                                                                    \
    }                                                                      \
                                                                           \
   protected:                                                              \
    bool Load(const std::string &filename) override {                      \
      if (!_name##_model_load(filename, model_, vocab_)) {                 \
        return false;                                                      \
      }                                                                    \
      n_ctx_ = model_.hparams.n_ctx;                                       \
      return true;                                                         \
    }                                                                      \
                                                                           \
    bool Eval(const std::vector<gpt_vocab::id> &tokens, const int threads, \
              const int n_past) override {                                 \
      return _name##_eval(model_, threads, n_past, tokens, logits_,        \
                          mem_per_token_);                                 \
    }                                                                      \
                                                                           \
   private:                                                                \
    _name##_model model_;                                                  \
  }

#endif
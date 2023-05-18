# [C Transformers](https://github.com/marella/ctransformers) [![PyPI](https://img.shields.io/pypi/v/ctransformers)](https://pypi.org/project/ctransformers/) [![tests](https://github.com/marella/ctransformers/actions/workflows/tests.yml/badge.svg)](https://github.com/marella/ctransformers/actions/workflows/tests.yml) [![build](https://github.com/marella/ctransformers/actions/workflows/build.yml/badge.svg)](https://github.com/marella/ctransformers/actions/workflows/build.yml)

Python bindings for the Transformer models implemented in C/C++ using [GGML](https://github.com/ggerganov/ggml) library.

- [Supported Models](#supported-models)
- [Installation](#installation)
- [Usage](#usage)
  - [Hugging Face Hub](#hugging-face-hub)
  - [LangChain](#langchain)
- [Documentation](#documentation)
- [License](#license)

## Supported Models

| Models             | Model Type  |
| :----------------- | ----------- |
| GPT-2              | `gpt2`      |
| GPT-J, GPT4All-J   | `gptj`      |
| GPT-NeoX, StableLM | `gpt_neox`  |
| Dolly V2           | `dolly-v2`  |
| StarCoder          | `starcoder` |

More models coming soon.

## Installation

```sh
pip install ctransformers
```

## Usage

It provides a unified interface for all models:

```py
from ctransformers import AutoModelForCausalLM

llm = AutoModelForCausalLM.from_pretrained('/path/to/ggml-gpt-2.bin', model_type='gpt2')

print(llm('AI is going to'))
```

[Run in Google Colab](https://colab.research.google.com/drive/1GMhYMUAv_TyZkpfvUI1NirM8-9mCXQyL)

If you are getting `illegal instruction` error, try using `lib='avx'` or `lib='basic'`:

```py
llm = AutoModelForCausalLM.from_pretrained('/path/to/ggml-gpt-2.bin', model_type='gpt2', lib='avx')
```

It provides a generator interface for more control:

```py
tokens = llm.tokenize('AI is going to')

for token in llm.generate(tokens):
    print(llm.detokenize(token))
```

This allows you to use a custom tokenizer.

It also provides access to the low-level C API. See [Documentation](#documentation) section below.

### Hugging Face Hub

It can be used with models hosted on the Hub:

```py
llm = AutoModelForCausalLM.from_pretrained('marella/gpt-2-ggml')
```

If a model repo has multiple model files (`.bin` files), specify a model file using:

```py
llm = AutoModelForCausalLM.from_pretrained('marella/gpt-2-ggml', model_file='ggml-model.bin')
```

It can be used with your own models uploaded on the Hub. For better user experience, upload only one model per repo.

To use it with your own model, add `config.json` file to your model repo specifying the `model_type`:

```json
{
  "model_type": "gpt2"
}
```

You can also specify additional parameters under `task_specific_params.text-generation`:

```json
{
  "model_type": "gpt2",
  "task_specific_params": {
    "text-generation": {
      "top_k": 40,
      "top_p": 0.95,
      "temperature": 0.8,
      "repetition_penalty": 1.1,
      "last_n_tokens": 64
    }
  }
}
```

See [marella/gpt-2-ggml](https://huggingface.co/marella/gpt-2-ggml/blob/main/config.json) for a minimal example and [marella/gpt-2-ggml-example](https://huggingface.co/marella/gpt-2-ggml-example/blob/main/config.json) for a full example.

### LangChain

[LangChain](https://python.langchain.com/) is a framework for developing applications powered by language models. A LangChain LLM object can be created using:

```py
from ctransformers.langchain import CTransformers

llm = CTransformers(model='/path/to/ggml-gpt-2.bin', model_type='gpt2')

print(llm('AI is going to'))
```

If you are getting `illegal instruction` error, try using `lib='avx'` or `lib='basic'`:

```py
llm = CTransformers(model='/path/to/ggml-gpt-2.bin', model_type='gpt2', lib='avx')
```

It can also be used with models hosted on the Hugging Face Hub:

```py
llm = CTransformers(model='marella/gpt-2-ggml')
```

Additional parameters can be passed using the `config` parameter:

```py
config = {'max_new_tokens': 256, 'repetition_penalty': 1.1}

llm = CTransformers(model='marella/gpt-2-ggml', config=config)
```

It can be used with other LangChain modules:

```py
from langchain import PromptTemplate, LLMChain

template = """Question: {question}

Answer:"""

prompt = PromptTemplate(template=template, input_variables=['question'])

llm_chain = LLMChain(prompt=prompt, llm=llm)

print(llm_chain.run('What is AI?'))
```

## Documentation

### Parameters

| Name                 | Type        | Description                                              | Default |
| :------------------- | :---------- | :------------------------------------------------------- | :------ |
| `top_k`              | `int`       | The top-k value to use for sampling.                     | `40`    |
| `top_p`              | `float`     | The top-p value to use for sampling.                     | `0.95`  |
| `temperature`        | `float`     | The temperature to use for sampling.                     | `0.8`   |
| `repetition_penalty` | `float`     | The repetition penalty to use for sampling.              | `1.0`   |
| `last_n_tokens`      | `int`       | The number of last tokens to use for repetition penalty. | `64`    |
| `seed`               | `int`       | The seed value to use for sampling tokens.               | Random  |
| `max_new_tokens`     | `int`       | The maximum number of new tokens to generate.            | `256`   |
| `stop`               | `List[str]` | A list of sequences to stop generation when encountered. | `[]`    |
| `reset`              | `bool`      | Whether to reset the model state before generating text. | `True`  |
| `batch_size`         | `int`       | The batch size to use for evaluating tokens.             | `8`     |
| `threads`            | `int`       | The number of threads to use for evaluating tokens.      | Auto    |

<!-- API_DOCS -->

### <kbd>class</kbd> `AutoModelForCausalLM`

---

#### <kbd>classmethod</kbd> `AutoModelForCausalLM.from_pretrained`

```python
from_pretrained(
    model_path_or_repo_id: str,
    model_type: Optional[str] = None,
    model_file: Optional[str] = None,
    config: Optional[ctransformers.hub.AutoConfig] = None,
    lib: Optional[str] = None,
    **kwargs
) → LLM
```

Loads the language model from a local file or remote repo.

**Args:**

- <b>`model_path_or_repo_id`</b>: The path to a model file or directory or the name of a Hugging Face Hub model repo.
- <b>`model_type`</b>: The model type.
- <b>`model_file`</b>: The name of the model file in repo or directory.
- <b>`config`</b>: `AutoConfig` object.
- <b>`lib`</b>: The path to a shared library or one of `avx2`, `avx`, `basic`.

**Returns:**
`LLM` object.

### <kbd>class</kbd> `LLM`

### <kbd>method</kbd> `LLM.__init__`

```python
__init__(
    model_path: str,
    model_type: str,
    config: Optional[ctransformers.llm.Config] = None,
    lib: Optional[str] = None
)
```

Loads the language model from a local file.

**Args:**

- <b>`model_path`</b>: The path to a model file.
- <b>`model_type`</b>: The model type.
- <b>`config`</b>: `Config` object.
- <b>`lib`</b>: The path to a shared library or one of `avx2`, `avx`, `basic`.

---

##### <kbd>property</kbd> LLM.config

The config object.

---

##### <kbd>property</kbd> LLM.model_path

The path to the model file.

---

##### <kbd>property</kbd> LLM.model_type

The model type.

---

#### <kbd>method</kbd> `LLM.detokenize`

```python
detokenize(tokens: Sequence[int]) → str
```

Converts a list of tokens to text.

**Args:**

- <b>`tokens`</b>: The list of tokens.

**Returns:**
The combined text of all tokens.

---

#### <kbd>method</kbd> `LLM.eval`

```python
eval(
    tokens: Sequence[int],
    batch_size: Optional[int] = None,
    threads: Optional[int] = None
) → None
```

Evaluates a list of tokens.

**Args:**

- <b>`tokens`</b>: The list of tokens to evaluate.
- <b>`batch_size`</b>: The batch size to use for evaluating tokens. Default: `8`
- <b>`threads`</b>: The number of threads to use for evaluating tokens. Default: `-1`

---

#### <kbd>method</kbd> `LLM.generate`

```python
generate(
    tokens: Sequence[int],
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    temperature: Optional[float] = None,
    repetition_penalty: Optional[float] = None,
    last_n_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    batch_size: Optional[int] = None,
    threads: Optional[int] = None,
    reset: Optional[bool] = None
) → Generator[int, NoneType, NoneType]
```

Generates new tokens from a list of tokens.

**Args:**

- <b>`tokens`</b>: The list of tokens to generate tokens from.
- <b>`top_k`</b>: The top-k value to use for sampling. Default: `40`
- <b>`top_p`</b>: The top-p value to use for sampling. Default: `0.95`
- <b>`temperature`</b>: The temperature to use for sampling. Default: `0.8`
- <b>`repetition_penalty`</b>: The repetition penalty to use for sampling. Default: `1.0`
- <b>`last_n_tokens`</b>: The number of last tokens to use for repetition penalty. Default: `64`
- <b>`seed`</b>: The seed value to use for sampling tokens. Default: `-1`
- <b>`batch_size`</b>: The batch size to use for evaluating tokens. Default: `8`
- <b>`threads`</b>: The number of threads to use for evaluating tokens. Default: `-1`
- <b>`reset`</b>: Whether to reset the model state before generating text. Default: `True`

**Returns:**
The generated tokens.

---

#### <kbd>method</kbd> `LLM.is_eos_token`

```python
is_eos_token(token: int) → bool
```

Checks if a token is an end-of-sequence token.

**Args:**

- <b>`token`</b>: The token to check.

**Returns:**
`True` if the token is an end-of-sequence token else `False`.

---

#### <kbd>method</kbd> `LLM.reset`

```python
reset() → None
```

Resets the model state.

---

#### <kbd>method</kbd> `LLM.sample`

```python
sample(
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    temperature: Optional[float] = None,
    repetition_penalty: Optional[float] = None,
    last_n_tokens: Optional[int] = None,
    seed: Optional[int] = None
) → int
```

Samples a token from the model.

**Args:**

- <b>`top_k`</b>: The top-k value to use for sampling. Default: `40`
- <b>`top_p`</b>: The top-p value to use for sampling. Default: `0.95`
- <b>`temperature`</b>: The temperature to use for sampling. Default: `0.8`
- <b>`repetition_penalty`</b>: The repetition penalty to use for sampling. Default: `1.0`
- <b>`last_n_tokens`</b>: The number of last tokens to use for repetition penalty. Default: `64`
- <b>`seed`</b>: The seed value to use for sampling tokens. Default: `-1`

**Returns:**
The sampled token.

---

#### <kbd>method</kbd> `LLM.tokenize`

```python
tokenize(text: str) → List[int]
```

Converts a text into list of tokens.

**Args:**

- <b>`text`</b>: The text to tokenize.

**Returns:**
The list of tokens.

---

#### <kbd>method</kbd> `LLM.__call__`

```python
__call__(
    prompt: str,
    max_new_tokens: Optional[int] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    temperature: Optional[float] = None,
    repetition_penalty: Optional[float] = None,
    last_n_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    batch_size: Optional[int] = None,
    threads: Optional[int] = None,
    stop: Optional[Sequence[str]] = None,
    reset: Optional[bool] = None
) → str
```

Generates text from a prompt.

**Args:**

- <b>`prompt`</b>: The prompt to generate text from.
- <b>`max_new_tokens`</b>: The maximum number of new tokens to generate. Default: `256`
- <b>`top_k`</b>: The top-k value to use for sampling. Default: `40`
- <b>`top_p`</b>: The top-p value to use for sampling. Default: `0.95`
- <b>`temperature`</b>: The temperature to use for sampling. Default: `0.8`
- <b>`repetition_penalty`</b>: The repetition penalty to use for sampling. Default: `1.0`
- <b>`last_n_tokens`</b>: The number of last tokens to use for repetition penalty. Default: `64`
- <b>`seed`</b>: The seed value to use for sampling tokens. Default: `-1`
- <b>`batch_size`</b>: The batch size to use for evaluating tokens. Default: `8`
- <b>`threads`</b>: The number of threads to use for evaluating tokens. Default: `-1`
- <b>`stop`</b>: A list of sequences to stop generation when encountered. Default: `None`
- <b>`reset`</b>: Whether to reset the model state before generating text. Default: `True`

**Returns:**
The generated text.

<!-- API_DOCS -->

## License

[MIT](https://github.com/marella/ctransformers/blob/main/LICENSE)
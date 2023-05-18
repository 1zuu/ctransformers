import inspect
import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from ctypes import (
    CDLL,
    c_bool,
    c_int,
    c_float,
    c_char_p,
    c_void_p,
    POINTER,
)
from typing import (
    Any,
    Callable,
    Generator,
    List,
    Optional,
    Sequence,
)

from .lib import find_library

c_int_p = POINTER(c_int)
llm_p = c_void_p


@dataclass
class Config:
    # sample
    top_k: int = 40
    top_p: float = 0.95
    temperature: float = 0.8
    repetition_penalty: float = 1.0
    last_n_tokens: int = 64
    seed: int = -1

    # eval
    batch_size: int = 8
    threads: int = -1

    # generate
    max_new_tokens: int = 256
    stop: Optional[Sequence[str]] = None
    reset: bool = True


docs = dict(
    top_k='The top-k value to use for sampling.',
    top_p='The top-p value to use for sampling.',
    temperature='The temperature to use for sampling.',
    repetition_penalty='The repetition penalty to use for sampling.',
    last_n_tokens='The number of last tokens to use for repetition penalty.',
    seed='The seed value to use for sampling tokens.',
    max_new_tokens='The maximum number of new tokens to generate.',
    stop='A list of sequences to stop generation when encountered.',
    reset='Whether to reset the model state before generating text.',
    batch_size='The batch size to use for evaluating tokens.',
    threads='The number of threads to use for evaluating tokens.',
)

for k in docs:
    docs[k] = f'{k}: {docs[k]} Default: `{getattr(Config, k)}`'


def doc(fn):
    doc = []
    for param in inspect.signature(fn).parameters:
        if param in docs:
            doc.append(docs[param])
    doc = ('\n' + ' ' * 12).join(doc)
    fn.__doc__ = fn.__doc__.format(params=doc)
    return fn


def get(*values):
    for value in values:
        if value is not None:
            return value


def load_library(path: Optional[str] = None) -> Any:
    path = find_library(path)
    lib = CDLL(path)

    lib.ctransformers_llm_create.argtypes = [c_char_p, c_char_p]
    lib.ctransformers_llm_create.restype = llm_p

    lib.ctransformers_llm_delete.argtypes = [llm_p]
    lib.ctransformers_llm_delete.restype = None

    lib.ctransformers_llm_tokenize.argtypes = [llm_p, c_char_p, c_int_p]
    lib.ctransformers_llm_tokenize.restype = c_int

    lib.ctransformers_llm_detokenize.argtypes = [llm_p, c_int]
    lib.ctransformers_llm_detokenize.restype = c_char_p

    lib.ctransformers_llm_is_eos_token.argtypes = [llm_p, c_int]
    lib.ctransformers_llm_is_eos_token.restype = c_bool

    lib.ctransformers_llm_batch_eval.argtypes = [llm_p, c_int_p, c_int, c_int]
    lib.ctransformers_llm_batch_eval.restype = c_bool

    lib.ctransformers_llm_sample.argtypes = [
        llm_p,
        c_int,  # top_k
        c_float,  # top_p
        c_float,  # temperature
        c_float,  # repetition_penalty
        c_int,  # last_n_tokens
        c_int,  # seed
    ]
    lib.ctransformers_llm_sample.restype = c_int

    lib.ctransformers_llm_reset.argtypes = [llm_p]
    lib.ctransformers_llm_reset.restype = None

    return lib


class LLM:

    def __init__(
        self,
        model_path: str,
        model_type: str,
        *,
        config: Optional[Config] = None,
        lib: Optional[str] = None,
    ):
        """
        Loads the language model from a local file.

        Args:
            model_path: The path to a model file.
            model_type: The model type.
            config: `Config` object.
            lib: The path to a shared library or one of `avx2`, `avx`, `basic`.
        """
        self._model_path = model_path
        self._model_type = model_type
        self._config = config or Config()
        self._llm = None
        self._lib = None

        if not Path(model_path).is_file():
            raise ValueError(f"Model path '{model_path}' doesn't exist.")

        self._lib = load_library(lib)
        self._llm = self._lib.ctransformers_llm_create(model_path.encode(),
                                                       model_type.encode())
        if self._llm is None:
            raise RuntimeError(
                f"Failed to create LLM '{model_type}' from '{model_path}'.")

    @property
    def model_path(self) -> str:
        """The path to the model file."""
        return self._model_path

    @property
    def model_type(self) -> str:
        """The model type."""
        return self._model_type

    @property
    def config(self) -> Config:
        """The config object."""
        return self._config

    def __getattr__(self, name: str) -> Callable:
        lib, llm = self._lib, self._llm
        if name.startswith('ctransformers_llm_') and hasattr(lib, name):
            return partial(getattr(lib, name), llm)
        raise AttributeError(f"'LLM' object has no attribute '{name}'")

    def tokenize(self, text: str) -> List[int]:
        """
        Converts a text into list of tokens.

        Args:
            text: The text to tokenize.

        Returns:
            The list of tokens.
        """
        tokens = (c_int * len(text))()
        n_tokens = self.ctransformers_llm_tokenize(text.encode(), tokens)
        return tokens[:n_tokens]

    def detokenize(self, tokens: Sequence[int]) -> str:
        """
        Converts a list of tokens to text.

        Args:
            tokens: The list of tokens.

        Returns:
            The combined text of all tokens.
        """
        if isinstance(tokens, int):
            tokens = [tokens]
        texts = []
        for token in tokens:
            text = self.ctransformers_llm_detokenize(token)
            texts.append(text.decode())
        return ''.join(texts)

    def is_eos_token(self, token: int) -> bool:
        """
        Checks if a token is an end-of-sequence token.

        Args:
            token: The token to check.

        Returns:
            `True` if the token is an end-of-sequence token else `False`.
        """
        return self.ctransformers_llm_is_eos_token(token)

    @doc
    def eval(
        self,
        tokens: Sequence[int],
        *,
        batch_size: Optional[int] = None,
        threads: Optional[int] = None,
    ) -> None:
        """
        Evaluates a list of tokens.

        Args:
            tokens: The list of tokens to evaluate.
            {params}
        """
        config = self.config
        batch_size = get(batch_size, config.batch_size)
        threads = get(threads, config.threads)

        n_tokens = len(tokens)
        tokens = (c_int * n_tokens)(*tokens)
        status = self.ctransformers_llm_batch_eval(tokens, n_tokens,
                                                   batch_size, threads)
        if not status:
            raise RuntimeError('Failed to evaluate tokens.')

    @doc
    def sample(
        self,
        *,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        temperature: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        last_n_tokens: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> int:
        """
        Samples a token from the model.

        Args:
            {params}

        Returns:
            The sampled token.
        """
        config = self.config
        top_k = get(top_k, config.top_k)
        top_p = get(top_p, config.top_p)
        temperature = get(temperature, config.temperature)
        repetition_penalty = get(repetition_penalty, config.repetition_penalty)
        last_n_tokens = get(last_n_tokens, config.last_n_tokens)
        seed = get(seed, config.seed)

        return self.ctransformers_llm_sample(
            top_k,
            top_p,
            temperature,
            repetition_penalty,
            last_n_tokens,
            seed,
        )

    def reset(self) -> None:
        """
        Resets the model state.
        """
        self.ctransformers_llm_reset()

    def __del__(self):
        if self._llm is not None:
            self.ctransformers_llm_delete()

    @doc
    def generate(
        self,
        tokens: Sequence[int],
        *,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        temperature: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        last_n_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        batch_size: Optional[int] = None,
        threads: Optional[int] = None,
        reset: Optional[bool] = None,
    ) -> Generator[int, None, None]:
        """
        Generates new tokens from a list of tokens.

        Args:
            tokens: The list of tokens to generate tokens from.
            {params}

        Returns:
            The generated tokens.
        """
        config = self.config
        reset = get(reset, config.reset)

        if reset:
            self.reset()

        self.eval(tokens, batch_size=batch_size, threads=threads)
        while True:
            token = self.sample(
                top_k=top_k,
                top_p=top_p,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
                last_n_tokens=last_n_tokens,
                seed=seed,
            )
            self.eval([token], batch_size=batch_size, threads=threads)
            if self.is_eos_token(token):
                break
            yield token

    def _stream(
        self,
        prompt: str,
        *,
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
        reset: Optional[bool] = None,
    ) -> Generator[str, None, None]:
        config = self.config
        max_new_tokens = get(max_new_tokens, config.max_new_tokens)
        stop = get(stop, config.stop) or []
        if isinstance(stop, str):
            stop = [stop]

        tokens = self.tokenize(prompt)

        stop_regex = re.compile('|'.join(map(re.escape, stop)))
        count = 0
        text = ''
        for token in self.generate(
                tokens,
                top_k=top_k,
                top_p=top_p,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
                last_n_tokens=last_n_tokens,
                seed=seed,
                batch_size=batch_size,
                threads=threads,
                reset=reset,
        ):
            text += self.detokenize([token])

            # https://github.com/abetlen/llama-cpp-python/blob/1a13d76c487df1c8560132d10bda62d6e2f4fa93/llama_cpp/llama.py#L686-L706
            # Check if one of the stop sequences is part of the text.
            # Note that the stop sequence may not always be at the end of text.
            if stop:
                match = stop_regex.search(text)
                if match:
                    text = text[:match.start()]
                    break

            # Avoid sending the longest suffix of text which is also a prefix
            # of a stop sequence, as it can form a stop sequence with the text
            # generated later.
            longest = 0
            for s in stop:
                for i in range(len(s), 0, -1):
                    if text.endswith(s[:i]):
                        longest = max(i, longest)
                        break

            end = len(text) - longest
            if end > 0:
                yield text[:end]
                text = text[end:]

            count += 1
            if count >= max_new_tokens:
                break

        if text:
            yield text

    @doc
    def __call__(
        self,
        prompt: str,
        *,
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
        reset: Optional[bool] = None,
    ) -> str:
        """
        Generates text from a prompt.

        Args:
            prompt: The prompt to generate text from.
            {params}

        Returns:
            The generated text.
        """
        text = self._stream(
            prompt,
            max_new_tokens=max_new_tokens,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            last_n_tokens=last_n_tokens,
            seed=seed,
            batch_size=batch_size,
            threads=threads,
            stop=stop,
            reset=reset,
        )
        return ''.join(text)